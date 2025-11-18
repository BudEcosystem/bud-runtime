import logging
from typing import Any, Dict, Optional, Tuple

from llm_benchmark.model import analysis


# Try to import llm-memory-calculator for accurate calculations
try:
    from llm_memory_calculator import calculate_memory

    LLM_CALC_AVAILABLE = True
except ImportError:
    logging.warning("llm-memory-calculator not available, falling back to llm_benchmark analysis")
    LLM_CALC_AVAILABLE = False

logger = logging.getLogger(__name__)


class ModelAnalysis:
    def __init__(
        self,
        model: str,
        device_config: Dict[str, Any],
        input_tokens: int,
        output_tokens: int,
        concurrency: int,
        tp_size: int,
        pp_size: int = 1,
    ):
        """Initialize ModelAnalysis.

        Args:
            model (str): The name or path of the model to analyze.
            device_config (dict): Configuration of the device to use for analysis.
            input_tokens (int): Number of input tokens.
            output_tokens (int): Number of output tokens to generate.
            concurrency (int): Number of concurrent requests.
            tp_size (int): Tensor parallelism size.
            pp_size (int): Pipeline parallelism size (default 1).
        """
        self.model = model
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.tp_size = tp_size
        self.pp_size = pp_size
        self.concurrency = concurrency

        # Store original device config before transformation (for llm-memory-calculator)
        self._original_device_config = device_config.copy()

        # Transform device config for GPUConfig compatibility
        self.device_config = self._prepare_device_config_for_gpu_config(device_config)

        self.model_analysis = analysis.infer(
            model_name=self.model,
            device_config=self.device_config,
            seq_len=self.input_tokens,
            num_tokens_to_generate=self.output_tokens,
            batch_size_per_gpu=self.concurrency,
            tp_size=self.tp_size,
            pp_size=self.pp_size,  # Add PP size support
            log_level="ERROR",
        )

    def _prepare_device_config_for_gpu_config(self, device_config: Dict[str, Any]) -> Dict[str, Any]:
        """Transform device config to format expected by GPUConfig.

        GPUConfig expects specific field names with exact casing and requires certain fields.
        This method converts from our internal format to GPUConfig format.
        """
        # Start with a copy to avoid modifying the original
        config = device_config.copy()

        # Remove cluster context and extra fields that GPUConfig doesn't expect
        unwanted_fields = [
            "cluster_id",
            "node_id",
            "node_name",
            "node_devices",
            "cluster_topology",
            "id",
            "type",
            "device_id",
            "device_type",
            "total_devices",
            "node_distribution",
            "devices_by_node",
            "max_devices_per_node",
            "total_nodes_with_device",
        ]
        for field in unwanted_fields:
            config.pop(field, None)

        # Transform keys to GPUConfig expected format
        gpu_config = {}

        # Required field: name (GPUConfig needs this)
        gpu_config["name"] = config.get("device_name") or config.get("name") or "Unknown_Device"

        # Memory field - convert lowercase to uppercase format
        if "mem_per_gpu_in_gb" in config:
            gpu_config["mem_per_GPU_in_GB"] = config["mem_per_gpu_in_gb"]
        elif "mem_per_GPU_in_GB" in config:
            gpu_config["mem_per_GPU_in_GB"] = config["mem_per_GPU_in_GB"]
        else:
            gpu_config["mem_per_GPU_in_GB"] = 0  # Default fallback

        # Performance fields - convert lowercase to uppercase format
        if "peak_fp16_tflops" in config:
            gpu_config["peak_fp16_TFLOPS"] = config["peak_fp16_tflops"]
        elif "peak_fp16_TFLOPS" in config:
            gpu_config["peak_fp16_TFLOPS"] = config["peak_fp16_TFLOPS"]
        else:
            # Default for A100 80GB if not specified
            gpu_config["peak_fp16_TFLOPS"] = 312

        # Bandwidth fields - convert lowercase to uppercase format
        if "hbm_bandwidth_in_gb_per_sec" in config:
            gpu_config["hbm_bandwidth_in_GB_per_sec"] = config["hbm_bandwidth_in_gb_per_sec"]
        elif "hbm_bandwidth_in_GB_per_sec" in config:
            gpu_config["hbm_bandwidth_in_GB_per_sec"] = config["hbm_bandwidth_in_GB_per_sec"]
        else:
            # Default for A100 80GB if not specified
            gpu_config["hbm_bandwidth_in_GB_per_sec"] = 1935

        if "intra_node_bandwidth_in_gb_per_sec" in config:
            gpu_config["intra_node_bandwidth_in_GB_per_sec"] = config["intra_node_bandwidth_in_gb_per_sec"]
        elif "intra_node_bandwidth_in_GB_per_sec" in config:
            gpu_config["intra_node_bandwidth_in_GB_per_sec"] = config["intra_node_bandwidth_in_GB_per_sec"]
        else:
            # Default NVLink bandwidth
            gpu_config["intra_node_bandwidth_in_GB_per_sec"] = 300

        if "inter_node_bandwidth_in_gb_per_sec" in config:
            gpu_config["inter_node_bandwidth_in_GB_per_sec"] = config["inter_node_bandwidth_in_gb_per_sec"]
        elif "inter_node_bandwidth_in_GB_per_sec" in config:
            gpu_config["inter_node_bandwidth_in_GB_per_sec"] = config["inter_node_bandwidth_in_GB_per_sec"]
        else:
            # Default InfiniBand bandwidth
            gpu_config["inter_node_bandwidth_in_GB_per_sec"] = 200

        # Required latency field
        if "intra_node_min_message_latency" in config:
            gpu_config["intra_node_min_message_latency"] = config["intra_node_min_message_latency"]
        else:
            # Default latency for NVLink
            gpu_config["intra_node_min_message_latency"] = 8e-06

        # Available count field
        gpu_config["available_count"] = config.get("available_count", 1)

        return gpu_config

    def analyze(self) -> Dict[str, Any]:
        """Perform model analysis.

        Returns:
            dict: Analysis results from the model.
        """
        if isinstance(self.model_analysis, dict):
            return self.model_analysis
        else:
            raise TypeError("Expected model_analysis to be of type dict")

    def get_max_concurrency(self, memory: float) -> int:
        """Get the maximum concurrency for the model."""
        model_weight_per_gpu = self.model_analysis["weight_memory_per_gpu"] / (1024**3)  # Convert to GB
        kv_cache_memory_per_gpu = self.model_analysis["kv_cache_memory_per_gpu"] / (1024**3)  # Convert to GB

        memory_available_for_kv_cache = memory - model_weight_per_gpu
        max_concurrency = memory_available_for_kv_cache / kv_cache_memory_per_gpu

        return int(max_concurrency)

    def get_model_parameters(self) -> Optional[int]:
        """Get model parameter count using llm-memory-calculator.

        Returns:
            Optional[int]: Number of model parameters, or None if calculation fails
        """
        if not LLM_CALC_AVAILABLE:
            logger.warning("llm-memory-calculator not available, cannot get accurate parameter count")
            return None

        try:
            # Use calculate_memory to get model memory report
            # Add 10% safety margin to match deployment configuration
            seq_length = int((self.input_tokens + self.output_tokens) * 1.1)
            memory_report = calculate_memory(
                model_id_or_config=self.model,
                batch_size=1,  # Use 1 for parameter counting
                seq_length=seq_length,
                precision="bf16",  # Default to BF16
                tensor_parallel=self.tp_size,  # Pass TP for correct per-device calculations
            )

            # Extract parameter count from memory report
            if hasattr(memory_report, "parameter_count"):
                return memory_report.parameter_count
            elif hasattr(memory_report, "total_parameters"):
                return memory_report.total_parameters
            elif hasattr(memory_report, "parameters"):
                return memory_report.parameters
            elif hasattr(memory_report, "model_parameters"):
                return memory_report.model_parameters
            else:
                logger.warning("Could not extract parameter count from memory report")
                logger.debug(f"Available attributes: {dir(memory_report)}")
                return None

        except Exception as e:
            logger.error(f"Error calculating model parameters with llm-memory-calculator: {e}")
            return None

    def get_model_weight_and_kv_cache(self, bits: int = 16) -> Tuple[Optional[float], Optional[float]]:
        """Get accurate model weight and KV cache requirements using llm-memory-calculator.

        Args:
            bits: Precision bits (16 for FP16, 8 for INT8, etc.)

        Returns:
            Tuple[Optional[float], Optional[float]]: (model_weight_gb, kv_cache_per_request_gb)
                                                   Returns (None, None) if calculation fails
        """
        if not LLM_CALC_AVAILABLE:
            logger.warning("llm-memory-calculator not available, cannot get accurate memory requirements")
            return None, None

        try:
            # Map bits to string format
            precision = "bf16"  # Default
            if bits == 8 or "int8" in str(bits).lower():
                precision = "int8"
            elif bits == 4 or "int4" in str(bits).lower():
                precision = "int4"
            elif bits == 16:
                precision = "bf16"

            # Calculate memory requirements using calculate_memory
            # Use actual concurrency for accurate KV cache calculation
            # Add 10% safety margin to match deployment configuration
            seq_length = int((self.input_tokens + self.output_tokens) * 1.1)
            memory_report = calculate_memory(
                model_id_or_config=self.model,
                batch_size=self.concurrency,  # Use actual concurrency for total KV cache
                seq_length=seq_length,
                precision=precision,
                tensor_parallel=self.tp_size,  # Pass TP for correct per-device calculations
                respect_weight_tying=False,
            )

            # Extract model weight and KV cache from memory report
            model_weight_gb = None
            kv_cache_per_request_gb = None

            # Check available attributes
            if hasattr(memory_report, "weight_memory_gb"):
                model_weight_gb = memory_report.weight_memory_gb
            elif hasattr(memory_report, "model_memory_gb"):
                model_weight_gb = memory_report.model_memory_gb
            elif hasattr(memory_report, "model_memory"):
                model_weight_gb = memory_report.model_memory / (1024**3)  # Convert bytes to GB

            # KV cache is calculated for total concurrency, divide by concurrency to get per-request
            if hasattr(memory_report, "kv_cache_gb") and self.concurrency > 0:
                kv_cache_per_request_gb = memory_report.kv_cache_gb / self.concurrency
            elif hasattr(memory_report, "kv_cache_memory_gb") and self.concurrency > 0:
                kv_cache_per_request_gb = memory_report.kv_cache_memory_gb / self.concurrency
            elif hasattr(memory_report, "kv_cache_memory") and self.concurrency > 0:
                kv_cache_per_request_gb = (memory_report.kv_cache_memory / (1024**3)) / self.concurrency

            if model_weight_gb is None or kv_cache_per_request_gb is None:
                logger.warning("Could not extract memory requirements from memory report")
                logger.debug(f"Memory report type: {type(memory_report)}")
                logger.debug(f"Available attributes: {dir(memory_report)}")

            return model_weight_gb, kv_cache_per_request_gb

        except Exception as e:
            logger.error(f"Error calculating memory requirements with llm-memory-calculator: {e}")
            return None, None

    def get_accurate_max_concurrency(self, gpu_memory_gb: float, bits: int = 16) -> int:
        """Get accurate maximum concurrency using llm-memory-calculator.

        Args:
            gpu_memory_gb: Available GPU memory in GB
            bits: Model precision bits

        Returns:
            int: Maximum concurrency that fits in GPU memory
        """
        model_weight_gb, kv_cache_per_request_gb = self.get_model_weight_and_kv_cache(bits)

        if model_weight_gb is None or kv_cache_per_request_gb is None:
            logger.warning("Could not get accurate memory requirements, falling back to original calculation")
            return self.get_max_concurrency(gpu_memory_gb)

        # Reserve some memory for system overhead
        available_memory_gb = gpu_memory_gb * 0.95  # Use 95% of available memory

        # Calculate available memory for KV cache
        memory_for_kv_cache = available_memory_gb - model_weight_gb

        if memory_for_kv_cache <= 0:
            logger.warning(
                f"Model weight ({model_weight_gb:.2f}GB) exceeds available memory ({available_memory_gb:.2f}GB)"
            )
            return 0

        # Calculate max concurrency
        max_concurrency = int(memory_for_kv_cache / kv_cache_per_request_gb)

        logger.info(
            f"Accurate memory calculation: Model={model_weight_gb:.2f}GB, "
            f"KV_cache_per_request={kv_cache_per_request_gb:.4f}GB, "
            f"Max_concurrency={max_concurrency}"
        )

        return max(1, max_concurrency)  # Ensure at least 1

    def get_total_memory_requirement(self, bits: int = 16) -> Optional[float]:
        """Get total memory requirement for current configuration.

        This includes model weights and KV cache for all concurrent requests.

        Args:
            bits: Model precision bits

        Returns:
            Optional[float]: Total memory requirement in GB, or None if calculation fails
        """
        if not LLM_CALC_AVAILABLE:
            # Fallback to old calculation
            model_weight_gb = self.model_analysis.get("weight_memory_per_gpu", 0) / (1024**3)
            kv_cache_total_gb = self.model_analysis.get("kv_cache_memory_per_gpu", 0) / (1024**3)
            return model_weight_gb + kv_cache_total_gb

        try:
            # Map bits to string format
            precision = "bf16"  # Default
            if bits == 8 or "int8" in str(bits).lower():
                precision = "int8"
            elif bits == 4 or "int4" in str(bits).lower():
                precision = "int4"
            elif bits == 16:
                precision = "bf16"

            # Calculate total memory requirements
            # Add 10% safety margin to match deployment configuration
            seq_length = int((self.input_tokens + self.output_tokens) * 1.1)
            memory_report = calculate_memory(
                model_id_or_config=self.model,
                batch_size=self.concurrency,
                seq_length=seq_length,
                precision=precision,
                tensor_parallel=self.tp_size,  # Pass TP for correct per-device calculations
                respect_weight_tying=False,
            )

            # Return total memory in GB
            if hasattr(memory_report, "total_memory_gb"):
                return memory_report.total_memory_gb
            elif hasattr(memory_report, "total_memory_bytes"):
                return memory_report.total_memory_bytes / (1024**3)
            else:
                logger.warning("Could not extract total memory from memory report")
                return None

        except Exception as e:
            logger.error(f"Error calculating total memory requirement: {e}")
            return None

    def _get_hardware_config_for_llm_calc(self) -> Optional[str]:
        """Get hardware configuration string for llm-memory-calculator.

        Returns:
            Optional[str]: Hardware config string (e.g., "A100_80GB_GPU") or None if not found
        """
        if not LLM_CALC_AVAILABLE:
            return None

        try:
            # Get original device config before transformation (which removes type field)
            original_config = getattr(self, "_original_device_config", self.device_config)

            # Extract device type and memory from original device config
            device_type = original_config.get("type", "")
            device_name = original_config.get("name", "")
            memory_gb = original_config.get("mem_per_GPU_in_GB", 0)

            logger.debug(f"Hardware detection: type={device_type}, name={device_name}, memory={memory_gb}GB")

            # Map to llm-memory-calculator hardware configs (system names from system_configs.py)
            if device_type == "cuda":
                if "H100" in device_name:
                    return "H100_GPU"
                elif "A100" in device_name:
                    if memory_gb >= 80:
                        return "A100_80GB_GPU"
                    else:
                        return "A100_40GB_GPU"
                elif "MI300X" in device_name:
                    return "MI300X"
                elif "MI325X" in device_name:
                    return "MI325X"
                else:
                    # Default to A100_80GB_GPU for other CUDA devices
                    logger.info(f"Unknown CUDA device {device_name}, defaulting to A100_80GB_GPU")
                    return "A100_80GB_GPU"
            elif device_type == "hpu":
                # Intel Gaudi devices
                return "Gaudi3"
            else:
                logger.warning(f"Unsupported device type: {device_type}, defaulting to A100_80GB_GPU")
                return "A100_80GB_GPU"

        except Exception as e:
            logger.error(f"Error determining hardware config: {e}")
            return "A100_80GB_GPU"  # Safe fallback
