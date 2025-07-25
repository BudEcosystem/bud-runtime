from typing import Any, Dict

from llm_benchmark.model import analysis


class ModelAnalysis:
    def __init__(
        self,
        model: str,
        device_config: Dict[str, Any],
        input_tokens: int,
        output_tokens: int,
        concurrency: int,
        tp_size: int,
    ):
        """Initialize ModelAnalysis.

        Args:
            model (str): The name or path of the model to analyze.
            device_config (dict): Configuration of the device to use for analysis.
            input_tokens (int): Number of input tokens.
            output_tokens (int): Number of output tokens to generate.
            concurrency (int): Number of concurrent requests.
            tp_size (int): Tensor parallelism size.
        """
        self.model = model
        self.device_config = device_config
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.tp_size = tp_size
        self.concurrency = concurrency

        self.device_config.pop("cluster_id", None)
        self.device_config.pop("node_id", None)
        self.device_config.pop("node_name", None)
        self.device_config.pop("id", None)
        self.device_config.pop("type", None)

        self.model_analysis = analysis.infer(
            model_name=self.model,
            device_config=self.device_config,
            seq_len=self.input_tokens,
            num_tokens_to_generate=self.output_tokens,
            batch_size_per_gpu=self.concurrency,
            tp_size=self.tp_size,
            log_level="ERROR",
        )

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
