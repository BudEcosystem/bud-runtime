"""Direct Search Optimizer - A deterministic alternative to Evolution algorithm.

This optimizer starts from minimal hardware configuration (TP=1, PP=1) with maximum
concurrency and explores configurations systematically, stopping when performance
targets are met to ensure minimum cost.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from budmicroframe.commons import logging

from ..engine_ops import check_config_compatibility, get_engine_properties
from ..model_ops.analysis import ModelAnalysis
from .hardware import CostCalculator
from .heuristic import HeuristicCalculator
from .regressor import BenchmarkPredictor


logger = logging.get_logger(__name__)


@dataclass
class SearchResult:
    """Result from direct search optimization."""

    config: Dict[str, Any]
    total_memory: float
    ttft: float
    e2e_latency: float
    throughput_per_user: float
    concurrency: int
    error_rate: float
    cost_per_million_tokens: float
    performance_penalty: float
    meets_targets: bool
    search_step: int
    weight_memory: float = 0.0
    kv_cache_memory: float = 0.0
    max_loras: Optional[int] = None  # Optimal max_loras if LoRA supported


class DirectSearchOptimizer:
    """Direct Search Optimizer that systematically explores configurations.

    Strategy:
    1. Start with TP=1, PP=1, max_concurrency (lowest cost if targets met)
    2. If targets not met, reduce concurrency step by step
    3. If TP=1 exhausted, try TP=2, then TP=4, etc.
    4. For each TP, start again from max_concurrency
    5. Stop at first configuration that meets all targets (guaranteed lowest cost)
    """

    def __init__(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        max_concurrency: int,
        target_ttft: float,
        target_throughput_per_user: float,
        target_e2e_latency: float,
        device_config: Dict[str, Any],
        engine_name: str,
        dtype: Optional[str] = None,
        model_uri: Optional[str] = None,  # HuggingFace model identifier
        benchmark_predictor_models_dir: Optional[str] = None,
        error_threshold: float = 0.01,
        use_heuristic: bool = False,
        concurrency_step: int = 5,  # Step size for concurrency reduction
        max_evaluations: int = 200,  # Safety limit
        supports_pipeline_parallelism: bool = False,
        hardware_mode: str = "dedicated",  # Hardware utilization mode
        is_quantization: bool = False,
        supports_lora: bool = False,
        model_max_context_length: Optional[int] = None,
    ):
        """Initialize DirectSearchOptimizer."""
        self.model = model
        self.model_uri = model_uri  # Store the HuggingFace model identifier for reference
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.model_max_context_length = model_max_context_length
        self.max_concurrency = max_concurrency
        self.target_ttft = target_ttft
        self.target_throughput_per_user = target_throughput_per_user
        self.target_e2e_latency = target_e2e_latency
        self.device_config = device_config
        self.engine_name = engine_name
        self.dtype = dtype
        self.error_threshold = error_threshold
        self.use_heuristic = use_heuristic
        self.concurrency_step = concurrency_step
        self.max_evaluations = max_evaluations
        self.supports_pipeline_parallelism = supports_pipeline_parallelism
        self.hardware_mode = hardware_mode
        self.is_quantization = is_quantization
        self.supports_lora = supports_lora
        self._last_validation_result = None  # Initialize validation result cache

        self.engine_config = get_engine_properties(self.engine_name, {"model": self.model})

        # Initialize predictor
        if self.use_heuristic:
            self.heuristic_calculator = HeuristicCalculator()
            logger.info("Using heuristic-based performance calculations")
        else:
            self.benchmark_predictor = BenchmarkPredictor(
                self.engine_name,
                self.device_config.get("device_type", self.device_config.get("type", "cpu")),
                benchmark_predictor_models_dir,
            )
            logger.info("Using ML regressor-based performance predictions")

        self.cost_calculator = CostCalculator()

        # Cache for avoiding redundant evaluations
        self._evaluation_cache = {}
        self.evaluated_configs = []
        # Cache for storing optimal max_loras per configuration
        self._max_loras_cache = {}

        # Get valid TP/PP ranges from device constraints
        self._init_search_space()

    def _init_search_space(self) -> None:
        """Initialize the search space based on device constraints."""
        # Get max devices per node for TP constraint
        if "node_distribution" in self.device_config:
            # Cluster-aware configuration from grouped devices
            self.max_tp = self.device_config.get("max_devices_per_node", 1)
            self.max_pp = self.device_config.get("total_nodes_with_device", 1)
            logger.info(
                f"Using cluster-aware search space: device_type={self.device_config.get('device_type')}, "
                f"max_tp={self.max_tp} (max devices/node), max_pp={self.max_pp} (nodes with device)"
            )
        else:
            # Fallback for individual device (shouldn't happen with new workflow)
            self.max_tp = self.device_config.get("available_count", 1)
            cluster_topology = self.device_config.get("cluster_topology", {})
            self.max_pp = cluster_topology.get("total_nodes", 1)
            # If no cluster topology and no available_count, default to 1
            if self.max_tp == 0:
                self.max_tp = 1
            if self.max_pp == 0:
                self.max_pp = 1
            logger.warning(
                f"Using fallback search space (individual device): max_tp={self.max_tp}, max_pp={self.max_pp}"
            )

        # Override max_pp to 1 if engine doesn't support pipeline parallelism
        if not self.supports_pipeline_parallelism:
            logger.info("Engine does not support pipeline parallelism - constraining PP to 1")
            self.max_pp = 1

        # CPU devices don't support multi-node pipeline parallelism
        device_type = self.device_config.get("device_type", self.device_config.get("type", "")).lower()
        if device_type in ("cpu", "cpu_high"):
            logger.info("CPU device detected - constraining PP to 1 (single-node only)")
            self.max_pp = 1

        # Find minimum TP required to run the model (even with concurrency=1)
        self.min_tp = self._find_minimum_tp_required()

        # Valid TP sizes (powers of 2, starting from minimum required)
        self.valid_tp_sizes = []

        # Handle edge case where min_tp is 0 (model cannot fit on this device)
        if self.min_tp == 0 or self.max_tp == 0:
            logger.warning(
                f"Device cannot accommodate model {self.model}: min_tp={self.min_tp}, max_tp={self.max_tp}. "
                f"Skipping this device configuration."
            )
            # Leave valid_tp_sizes empty to indicate this device cannot be used
        else:
            tp = self.min_tp
            while tp <= self.max_tp:
                self.valid_tp_sizes.append(tp)
                tp *= 2
        # Valid PP sizes
        self.valid_pp_sizes = list(range(1, self.max_pp + 1))

        # Override for shared hardware mode: force TP=1, PP=1
        if self.hardware_mode == "shared":
            logger.debug("Shared hardware mode: constraining to TP=1, PP=1 (no tensor/pipeline parallelism)")
            self.valid_tp_sizes = [1]
            self.valid_pp_sizes = [1]
            self.min_tp = 1

        logger.debug(
            f"Search space: TP sizes {self.valid_tp_sizes} (min required: {self.min_tp}), PP sizes {self.valid_pp_sizes}, max_concurrency={self.max_concurrency}"
        )

    def _find_minimum_tp_required(self) -> int:
        """Find the minimum TP size required to run the model with concurrency=1."""
        # Get device memory for detailed logging
        device_memory_gb = (
            self.device_config.get("mem_per_gpu_in_gb")
            or self.device_config.get("mem_per_GPU_in_GB")
            or self.device_config.get("memory")
            or self.device_config.get("memory_gb")
            or self.device_config.get("gpu_memory_gb")
            or 0
        )

        device_type = self.device_config.get("device_type", self.device_config.get("type", "unknown"))
        logger.info(
            f"Finding minimum TP for {self.model} on {device_type} with {device_memory_gb:.2f}GB memory, "
            f"max_tp={self.max_tp}"
        )

        # Try TP sizes in powers of 2: 1, 2, 4, 8, etc.
        max_possible_tp = self.max_tp

        # Test with concurrency=1 to find the absolute minimum TP required
        for tp in [1, 2, 4, 8, 16, 32]:
            if tp > max_possible_tp:
                break

            # Test if this TP can handle concurrency=1 (minimum viable configuration)
            if self._check_memory_requirements(tp, 1, 1):
                logger.info(f"Minimum TP required: {tp} for {self.model} on {device_type}")
                return tp

        # If we get here, even the highest TP can't fit the model
        logger.warning(
            f"Model {self.model} cannot fit on {device_type} device with {device_memory_gb:.2f}GB memory "
            f"even with maximum TP={max_possible_tp}. This device may be too small for this model."
        )
        return max_possible_tp  # Return max TP to avoid further attempts

    def _validate_config(self, tp_size: int, pp_size: int, concurrency: int) -> bool:
        """Validate if configuration is feasible."""
        # Check basic constraints
        if tp_size > self.max_tp or pp_size > self.max_pp:
            return False

        # Check total devices needed
        total_devices_needed = tp_size * pp_size

        if "node_distribution" in self.device_config:
            # Use total_devices from cluster config
            available_devices = self.device_config.get("total_devices", 0)
        else:
            # Fallback
            cluster_topology = self.device_config.get("cluster_topology", {})
            available_devices = cluster_topology.get("total_cluster_devices", 0)
            # If no cluster topology, use available_count
            if available_devices == 0:
                available_devices = self.device_config.get("available_count", 0)

        if total_devices_needed > available_devices:
            logger.debug(
                f"Not enough devices: need {total_devices_needed} (TP={tp_size} x PP={pp_size}), "
                f"have {available_devices} available"
            )
            return False

        # Additional check for TP constraint (devices must be on same node)
        if "max_devices_per_node" in self.device_config and tp_size > self.device_config["max_devices_per_node"]:
            logger.debug(f"TP={tp_size} exceeds max devices per node ({self.device_config['max_devices_per_node']})")
            return False

        # Check memory requirements and cache optimal max_loras
        fits, optimal_max_loras = self._check_memory_requirements(tp_size, pp_size, concurrency)
        if fits and optimal_max_loras is not None:
            # Cache the optimal max_loras for this configuration
            cache_key = (tp_size, pp_size, concurrency)
            self._max_loras_cache[cache_key] = optimal_max_loras
        return fits

    def _check_memory_requirements(self, tp_size: int, pp_size: int, concurrency: int) -> Tuple[bool, Optional[int]]:
        """Check if configuration fits in memory and find optimal max_loras if LoRA supported.

        Returns:
            Tuple[bool, Optional[int]]: (fits_in_memory, optimal_max_loras)
                - fits_in_memory: True if configuration fits
                - optimal_max_loras: Optimal max_loras value if LoRA supported, None otherwise
        """
        try:
            # Initialize HeuristicCalculator if not already done
            if not hasattr(self, "_heuristic_calc"):
                self._heuristic_calc = HeuristicCalculator()

            # Get total GPU memory from device config
            # Use explicit None check to handle 0 values correctly
            total_memory_gb = 0
            for key in ("mem_per_gpu_in_gb", "mem_per_GPU_in_GB", "memory", "memory_gb", "gpu_memory_gb"):
                if (mem := self.device_config.get(key)) is not None:
                    total_memory_gb = mem
                    break

            # Calculate available memory based on hardware mode
            hardware_mode = self.device_config.get("hardware_mode", "dedicated")
            memory_utilization_percent = self.device_config.get("memory_utilization_percent", 0)

            # Check if memory was already reduced upstream (workflows.py sets this marker)
            # When total_memory_gb_original is set, mem_per_GPU_in_GB already contains available memory
            memory_already_reduced = self.device_config.get("total_memory_gb_original") is not None

            if hardware_mode in ["shared", "time-slicing"]:
                if memory_already_reduced:
                    # Memory was already reduced in workflows.py, use as-is to avoid double reduction
                    available_memory_gb = total_memory_gb
                    original_total = self.device_config.get("total_memory_gb_original", total_memory_gb)
                    logger.info(
                        f"Shared GPU mode: Memory already reduced upstream "
                        f"(original={original_total:.2f}GB), using available_memory={available_memory_gb:.2f}GB"
                    )
                elif memory_utilization_percent > 0:
                    # Legacy path: reduce memory based on utilization percentage
                    available_memory_gb = total_memory_gb * (1 - memory_utilization_percent / 100.0)
                    logger.info(
                        f"Shared GPU mode detected: hardware_mode={hardware_mode}, "
                        f"total_memory={total_memory_gb:.2f}GB, "
                        f"utilization={memory_utilization_percent:.2f}%, "
                        f"available_memory={available_memory_gb:.2f}GB"
                    )
                else:
                    # Shared mode but no utilization data, use total memory
                    available_memory_gb = total_memory_gb
                    logger.debug(f"Shared GPU mode: No utilization data, using total_memory={total_memory_gb:.2f}GB")
            else:
                # For dedicated mode (or when hardware_mode not specified), use total memory
                available_memory_gb = total_memory_gb
                if hardware_mode not in ["shared", "time-slicing"]:
                    logger.debug(
                        f"Dedicated GPU mode: hardware_mode={hardware_mode}, "
                        f"using total_memory={total_memory_gb:.2f}GB"
                    )

            # Prepare model_params for validate_memory_requirements
            # Extract memory with fallback chain and log which key matched
            memory_in_gb = None
            memory_key_used = None
            for key in ["mem_per_gpu_in_gb", "mem_per_GPU_in_GB", "memory", "memory_gb", "gpu_memory_gb"]:
                if key in self.device_config and self.device_config[key] is not None:
                    memory_in_gb = self.device_config[key]
                    memory_key_used = key
                    break

            logger.debug(
                f"Memory extraction from device_config: memory_in_GB={memory_in_gb}, "
                f"key_used={memory_key_used}, hardware_mode={self.hardware_mode}, "
                f"TP={tp_size}, PP={pp_size}, concurrency={concurrency}"
            )

            model_params = {
                "model": self.model,
                "mean_input_tokens": self.input_tokens,
                "mean_output_tokens": self.output_tokens,
                "concurrent_requests": concurrency,
                "tensor_parallel_size": tp_size,
                "pipeline_parallel_size": pp_size,
                "memory_in_GB": available_memory_gb,
                "quantization_bits": 16,  # Default to 16-bit
            }

            # Check if LoRA is supported and optimize max_loras
            optimal_max_loras = None
            if self.supports_lora:
                optimal_max_loras = self._heuristic_calc.find_optimal_max_loras(
                    model_params=model_params,
                    max_lora_rank=256,
                    initial_max_loras=5,
                    min_max_loras=1,
                )

                if optimal_max_loras is None:
                    # Even min_max_loras=1 doesn't fit, configuration is invalid
                    logger.debug(
                        f"Memory check TP={tp_size}, PP={pp_size}, concurrency={concurrency}: "
                        f"Configuration doesn't fit even with min LoRA support"
                    )
                    return (False, None)

                logger.debug(
                    f"Memory check TP={tp_size}, PP={pp_size}, concurrency={concurrency}: "
                    f"Optimized max_loras={optimal_max_loras}"
                )

                # Store the validation result so memory values are available for shared mode evaluation
                # This mirrors the pattern used in the non-LoRA path (line 371)
                validation_result = self._heuristic_calc.validate_memory_requirements(
                    model_params={**model_params, "max_loras": optimal_max_loras},
                    max_loras=optimal_max_loras,
                    max_lora_rank=256,
                )
                self._last_validation_result = validation_result

                return (True, optimal_max_loras)
            else:
                # LoRA not supported, just check if base configuration fits
                validation_result = self._heuristic_calc.validate_memory_requirements(model_params)

                # Store validation result for later use (e.g., in shared mode to get memory value)
                self._last_validation_result = validation_result

                fits = validation_result["valid"]
                logger.debug(
                    f"Memory check TP={tp_size}, PP={pp_size}, concurrency={concurrency}: "
                    f"required={validation_result['total_memory_gb']:.2f}GB, "
                    f"available={validation_result['available_memory_gb']:.2f}GB, "
                    f"fits={fits}, message={validation_result['message']}"
                )
                return (fits, None)

        except Exception as e:
            logger.debug(f"Memory check failed for TP={tp_size}, PP={pp_size}, concurrency={concurrency}: {e}")
            return (False, None)

    def _evaluate_config(self, tp_size: int, pp_size: int, concurrency: int) -> Optional[SearchResult]:
        """Evaluate a single configuration."""
        config = {
            "tensor_parallel_size": tp_size,
            "pipeline_parallel_size": pp_size,
            "concurrency": concurrency,
            "target_device": self.device_config.get("device_type", self.device_config.get("type", "cpu")),
        }

        # Check cache first
        cache_key = (tp_size, pp_size, concurrency)
        if cache_key in self._evaluation_cache:
            return self._evaluation_cache[cache_key]

        # Validate configuration
        if not self._validate_config(tp_size, pp_size, concurrency):
            logger.debug(f"Invalid config: TP={tp_size}, PP={pp_size}, concurrency={concurrency}")
            return None

        # Check engine compatibility
        if not check_config_compatibility(self.engine_name, config):
            logger.debug(f"Engine {self.engine_name} not compatible with config: {config}")
            return None

        try:
            # Shared hardware mode: Skip performance prediction, only validate memory
            if self.hardware_mode == "shared":
                logger.info(
                    f"Shared mode: Memory validated for TP={tp_size}, PP={pp_size}, concurrency={concurrency}. "
                    "Skipping performance prediction."
                )

                # Get calculated memory from validation result
                weight_memory = 0.0
                total_memory = 0
                kv_cache_memory = 0.0
                if hasattr(self, "_last_validation_result") and self._last_validation_result:
                    total_memory_gb = self._last_validation_result.get("total_memory_gb", 0)
                    total_memory = total_memory_gb * (1024**3)  # Convert GB to Bytes
                    breakdown = self._last_validation_result.get("breakdown", {})
                    weight_memory = breakdown.get("weights", 0) * (1024**3)  # Convert GB to Bytes
                    kv_cache_memory = breakdown.get("kv_cache", 0) * (1024**3)  # Convert GB to Bytes
                    logger.debug(
                        f"Shared mode: total_memory_gb from validation={total_memory_gb:.4f}GB, breakdown={breakdown}"
                    )

                # Use the actual validation result to determine if config meets targets
                validation_passed = (
                    self._last_validation_result.get("valid", False)
                    if hasattr(self, "_last_validation_result") and self._last_validation_result
                    else False
                )

                # Log the validation decision for debugging
                if self._last_validation_result:
                    logger.debug(
                        f"Shared mode validation: meets_targets={validation_passed}, "
                        f"required={self._last_validation_result.get('total_memory_gb', 0):.2f}GB, "
                        f"available={self._last_validation_result.get('available_memory_gb', 0):.2f}GB, "
                        f"message={self._last_validation_result.get('message', 'N/A')}"
                    )

                # Calculate performance metrics and cost for shared mode (for reporting, not for ranking)
                # Performance targets are NOT checked - only memory validation determines meets_targets
                ttft = 0.0
                throughput_per_user = 0.0
                e2e_latency = 0.0
                cost_per_million_tokens = 0.0
                try:
                    data = self._prepare_predictor_data(config)
                    # Use full heuristic calculator to get all metrics (ttft, throughput, e2e_latency)
                    ttft, throughput_per_user, e2e_latency = self.heuristic_calculator(data)
                    # Apply quantization scaling to performance metrics (same as dedicated mode)
                    ttft, throughput_per_user, e2e_latency = self._apply_quantization_performance(
                        ttft, throughput_per_user, e2e_latency
                    )
                    cost_per_million_tokens = self.cost_calculator.get_cost_per_million_tokens(
                        throughput_per_user, concurrency, self.device_config, tp_size
                    )
                    logger.info(
                        f"Shared mode metrics calculated: TTFT={ttft:.2f}ms, E2E={e2e_latency:.2f}s, "
                        f"throughput={throughput_per_user:.2f} tok/s, cost=${cost_per_million_tokens:.6f}/M tokens "
                        f"(TP={tp_size}, concurrency={concurrency}, quantization={self.is_quantization})"
                    )
                except Exception as e:
                    logger.warning(f"Could not calculate metrics for shared mode: {e}. Using defaults.")

                # Retrieve cached optimal max_loras for this configuration
                optimal_max_loras = self._max_loras_cache.get(cache_key)

                # Return result with calculated metrics - meets_targets based on memory validation only
                result = SearchResult(
                    config=config,
                    total_memory=total_memory,
                    ttft=ttft,  # Calculated for reporting, not used for performance check
                    e2e_latency=e2e_latency,  # Calculated for reporting, not used for performance check
                    throughput_per_user=throughput_per_user,
                    concurrency=concurrency,
                    cost_per_million_tokens=cost_per_million_tokens,
                    performance_penalty=0,  # No performance requirements in shared mode
                    meets_targets=validation_passed,  # Based on memory validation only, not performance
                    search_step=len(self.evaluated_configs),
                    error_rate=0,
                    weight_memory=weight_memory,
                    kv_cache_memory=kv_cache_memory,
                    max_loras=optimal_max_loras,  # Include optimized max_loras
                )
                # Cache and store result
                self._evaluation_cache[cache_key] = result
                self.evaluated_configs.append(result)

                return result

            # Dedicated hardware mode: Full performance prediction
            # Prepare data for prediction
            data = self._prepare_predictor_data(config)

            # Get predictions
            if self.use_heuristic:
                ttft, throughput_per_user, e2e_latency = self.heuristic_calculator(data)
            else:
                ttft, throughput_per_user, e2e_latency = self.benchmark_predictor(data)

            # Apply quantization scaling
            ttft, throughput_per_user, e2e_latency = self._apply_quantization_performance(
                ttft, throughput_per_user, e2e_latency
            )

            # Calculate cost
            cost_per_million_tokens = self.cost_calculator.get_cost_per_million_tokens(
                throughput_per_user, concurrency, self.device_config, tp_size
            )
            logger.info(f"Cost calculated: ${cost_per_million_tokens:.6f}/M tokens for TP={tp_size}, PP={pp_size}")

            # Calculate performance penalty
            ttft_target_ms = self.target_ttft * 1000
            ttft_penalty = max(0, ttft / ttft_target_ms - 1)
            e2e_penalty = max(0, e2e_latency / self.target_e2e_latency - 1)
            throughput_penalty = max(0, 1 - throughput_per_user / self.target_throughput_per_user)

            performance_penalty = np.mean([ttft_penalty, e2e_penalty, throughput_penalty])
            meets_targets = performance_penalty <= self.error_threshold

            # Calculate Total Memory (Weights + KV + Overhead) for result
            # We use the value from validation which includes everything
            weight_memory = 0.0
            kv_cache_memory = 0.0
            if hasattr(self, "_last_validation_result") and self._last_validation_result:
                total_memory_gb = self._last_validation_result.get("total_memory_gb", 0)
                total_memory = total_memory_gb * (1024**3)  # Convert GB to Bytes
                # Extract weight and kv_cache memory from breakdown
                breakdown = self._last_validation_result.get("breakdown", {})
                weight_memory = breakdown.get("weights", 0) * (1024**3)
                kv_cache_memory = breakdown.get("kv_cache", 0) * (1024**3)
            else:
                # Fallback if validation result missing (shouldn't happen if validated)
                total_memory = data.get("kv_cache_memory_per_gpu", 0) * tp_size * pp_size
                weight_memory = data.get("weight_memory_per_gpu", 0) * (1024**3)
                kv_cache_memory = data.get("kv_cache_memory_per_gpu", 0)

            # Apply quantization performance scaling if needed
            if self.is_quantization:
                # Scale throughput up and memory down
                throughput_per_user = throughput_per_user * 1.3
                total_memory = total_memory * 0.5  # Approximate 50% reduction for 8-bit
                weight_memory = weight_memory * 0.5
                kv_cache_memory = kv_cache_memory * 0.5

            # Retrieve cached optimal max_loras for this configuration
            optimal_max_loras = self._max_loras_cache.get(cache_key)

            result = SearchResult(
                config=config,
                total_memory=total_memory,
                ttft=ttft,
                e2e_latency=e2e_latency,
                throughput_per_user=throughput_per_user,
                concurrency=concurrency,
                cost_per_million_tokens=cost_per_million_tokens,
                performance_penalty=performance_penalty,
                meets_targets=meets_targets,
                search_step=len(self.evaluated_configs),
                error_rate=performance_penalty,  # Use performance_penalty as error_rate for compatibility
                weight_memory=weight_memory,
                kv_cache_memory=kv_cache_memory,
                max_loras=optimal_max_loras,  # Include optimized max_loras
            )

            # Cache and store result
            self._evaluation_cache[cache_key] = result
            self.evaluated_configs.append(result)

            logger.info(
                f"Config evaluated: TP={tp_size}, PP={pp_size}, concurrency={concurrency} -> "
                f"TTFT={ttft:.1f}ms, Throughput={throughput_per_user:.1f}tok/s, E2E={e2e_latency:.2f}s, "
                f"Cost=${cost_per_million_tokens:.6f}/M, meets_targets={meets_targets}"
            )

            return result

        except Exception as e:
            logger.error(f"Error evaluating config TP={tp_size}, PP={pp_size}, concurrency={concurrency}: {e}")
            return None

    def _prepare_predictor_data(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare data for predictor (similar to Evolution's method)."""
        # Optimization: Skip expensive ModelAnalysis when using heuristic calculator
        if self.use_heuristic:
            # Heuristic calculator only needs basic simulation parameters and device info
            data = {
                "concurrent_requests": config["concurrency"],
                "tensor_parallel_size": config["tensor_parallel_size"],
                "pipeline_parallel_size": config.get("pipeline_parallel_size", 1),
                "mean_input_tokens": self.input_tokens,
                "mean_output_tokens": self.output_tokens,
                "model": self.model,
                "target_device": config.get("target_device", "cpu"),
                "memory_in_GB": (
                    self.device_config.get("mem_per_gpu_in_gb")
                    or self.device_config.get("mem_per_GPU_in_GB")
                    or self.device_config.get("memory")
                    or self.device_config.get("memory_gb")
                    or self.device_config.get("gpu_memory_gb")
                    or 0
                ),
                # Device identification fields for hardware matching
                "device_model": self.device_config.get("device_model", ""),
                "device_name": self.device_config.get("device_name", ""),
                "raw_name": self.device_config.get("raw_name", ""),
                "quantization": self.dtype or "",  # Default to empty string if dtype is None
                "model_max_context_length": self.model_max_context_length,  # Required for KV cache capping
            }
            # Calculate KV cache memory using heuristic calculator
            kv_cache_memory_per_gpu = self.heuristic_calculator.get_kv_cache_memory(data)
            data["kv_cache_memory_per_gpu"] = kv_cache_memory_per_gpu
            return data

        # ML-based predictor needs full ModelAnalysis
        device_config = self.device_config.copy()
        # Clean device config for ModelAnalysis
        for field in [
            "cluster_id",
            "node_id",
            "node_name",
            "id",
            "device_type",
            "node_distribution",
            "max_devices_per_node",
            "cluster_topology",
            "devices_by_node",
            "total_devices",
            "total_nodes_with_device",
        ]:
            device_config.pop(field, None)

        model_analysis = ModelAnalysis(
            model=self.model,
            device_config=device_config,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            concurrency=config["concurrency"],
            tp_size=config["tensor_parallel_size"],
            pp_size=config.get("pipeline_parallel_size", 1),
            model_max_context_length=self.model_max_context_length,
        )

        model_data = model_analysis.analyze()

        # Build data dict (simplified version of Evolution's method)
        data = {
            "concurrent_requests": config["concurrency"],
            "tensor_parallel_size": config["tensor_parallel_size"],
            "pipeline_parallel_size": config.get("pipeline_parallel_size", 1),
            "mean_input_tokens": self.input_tokens,
            "mean_output_tokens": self.output_tokens,
            "model": self.model,
            "target_device": config.get("target_device", "cpu"),  # Preserve target_device for heuristic calculator
            "memory_in_GB": self.device_config.get(
                "mem_per_GPU_in_GB", 0
            ),  # Memory field expected by heuristic calculator
            # Preserve device identification fields for hardware matching
            "device_model": self.device_config.get("device_model", ""),
            "device_name": self.device_config.get("device_name", ""),
            "raw_name": self.device_config.get("raw_name", ""),
            **model_data,  # Include all ModelAnalysis results
        }

        return data

    def _apply_quantization_performance(
        self, ttft: float, throughput_per_user: float, e2e_latency: float
    ) -> Tuple[float, float, float]:
        """Apply quantization performance scaling."""
        scale = 1.0
        if self.dtype == "bf16":
            scale = 1.0
        elif self.dtype == "INT8":
            scale = 1.3
        elif self.dtype == "INT4":
            scale = 1.5

        return ttft / scale, throughput_per_user * scale, e2e_latency / scale

    def search(self) -> List[SearchResult]:
        """Perform direct search optimization.

        Returns list of results, with the first one being the optimal (lowest cost that meets targets).
        """
        device_type = self.device_config.get("device_type", self.device_config.get("type", "unknown"))
        logger.info(
            f"Starting direct search for model {self.model} on {device_type} - "
            f"Valid TP sizes: {self.valid_tp_sizes}, Valid PP sizes: {self.valid_pp_sizes}"
        )
        logger.debug(
            f"Targets: TTFT<={self.target_ttft}s, E2E<={self.target_e2e_latency}s, Throughput>={self.target_throughput_per_user} tok/s"
        )

        best_result = None
        evaluations = 0

        # Search strategy: Start with minimum required hardware, max concurrency
        for pp_size in self.valid_pp_sizes:  # Start with PP=1 (cheapest)
            for tp_size in self.valid_tp_sizes:  # Start with minimum TP required (skip impossible configs)
                logger.debug(f"Searching TP={tp_size}, PP={pp_size}...")

                # Check if this TP size can potentially fit the model
                can_fit_at_any_concurrency = False
                # Start with lower concurrency values for memory testing, capped by max_concurrency
                test_concurrencies = [c for c in [1, 10, 50] if c <= self.max_concurrency]
                if not test_concurrencies:  # If max_concurrency is 0, at least test with 1
                    test_concurrencies = [1]

                for test_concurrency in test_concurrencies:
                    if self._validate_config(tp_size, pp_size, test_concurrency):
                        can_fit_at_any_concurrency = True
                        break

                if not can_fit_at_any_concurrency:
                    continue

                # Start from max concurrency, reduce step by step
                found_valid_config = False
                # Ensure we always test at least concurrency=1 when max_concurrency is small
                concurrency_values = list(range(self.max_concurrency, 0, -self.concurrency_step))
                if not concurrency_values or (1 not in concurrency_values and self.max_concurrency >= 1):
                    concurrency_values.append(1)

                for concurrency in sorted(concurrency_values, reverse=True):
                    # Safety check: if we've evaluated too many configs without finding a solution,
                    # and we haven't tried higher TP values yet, continue to ensure we explore all TP options
                    if evaluations >= self.max_evaluations and not best_result:
                        remaining_tp_values = [tp for tp in self.valid_tp_sizes if tp > tp_size]
                        if remaining_tp_values:
                            logger.warning(
                                f"Reached max evaluations ({self.max_evaluations}) but haven't found solution"
                            )
                            break  # Break from concurrency loop to try next TP
                        else:
                            logger.warning(f"Reached max evaluations limit: {self.max_evaluations}")
                            break  # Break from concurrency loop

                    result = self._evaluate_config(tp_size, pp_size, concurrency)
                    if result is None:
                        logger.debug(f"   Config TP={tp_size}, concurrency={concurrency} invalid")
                        continue

                    found_valid_config = True
                    evaluations += 1

                    if result.meets_targets:
                        logger.info(
                            f"Found optimal solution: TP={tp_size}, PP={pp_size}, concurrency={concurrency}, "
                            f"cost=${result.cost_per_million_tokens:.6f}/M tokens"
                        )

                        # This is optimal since we search from lowest cost configs first
                        best_result = result
                        break

                if not found_valid_config:
                    logger.debug(f"TP={tp_size} has no valid configurations")

                if best_result:
                    break  # Found optimal solution

                # Check if we should stop due to evaluation limit (only after trying this TP)
                if evaluations >= self.max_evaluations and not best_result:
                    remaining_tp_values = [tp for tp in self.valid_tp_sizes if tp > tp_size]
                    if not remaining_tp_values:
                        logger.warning("Reached max evaluations limit after exhausting all TP values")
                        break  # No more TP values to try

            if best_result:
                break  # Found optimal solution

        if not best_result and self.evaluated_configs:
            # No config met targets, return best effort (lowest penalty)
            best_result = min(self.evaluated_configs, key=lambda x: x.performance_penalty)
            device_type = self.device_config.get("type", self.device_config.get("device_type", "unknown"))
            logger.info(
                f"No configuration met all targets for {device_type} device. Best effort: "
                f"TP={best_result.config['tensor_parallel_size']}, PP={best_result.config['pipeline_parallel_size']}, "
                f"concurrency={best_result.concurrency}, penalty={best_result.performance_penalty:.4f}"
            )

        # Handle case where no valid configs were found (device too small for model)
        if not self.evaluated_configs:
            logger.error(
                f"No valid configurations found for model {self.model} on this device. "
                f"The device may not have enough memory to run this model."
            )
            return []

        # Return results sorted by cost (best first)
        results = sorted(self.evaluated_configs, key=lambda x: x.cost_per_million_tokens)
        return results[:5]  # Return top 5 like Evolution

    def get_search_summary(self) -> Dict[str, Any]:
        """Get summary of search process."""
        if not self.evaluated_configs:
            return {"total_evaluations": 0, "configs_meeting_targets": 0}

        meeting_targets = [r for r in self.evaluated_configs if r.meets_targets]

        return {
            "total_evaluations": len(self.evaluated_configs),
            "configs_meeting_targets": len(meeting_targets),
            "best_cost": min(r.cost_per_million_tokens for r in self.evaluated_configs),
            "best_penalty": min(r.performance_penalty for r in self.evaluated_configs),
            "tp_distribution": {
                tp: len([r for r in self.evaluated_configs if r.config["tensor_parallel_size"] == tp])
                for tp in self.valid_tp_sizes
            },
            "search_efficiency": len(meeting_targets) / len(self.evaluated_configs) if self.evaluated_configs else 0,
        }
