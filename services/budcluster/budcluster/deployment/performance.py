from typing import Dict, Optional
from uuid import UUID

from budmicroframe.commons.logging import get_logger
from llm_benchmark.benchmark import tools as benchmark_tools

from .utils import format_litellm_error_message


logger = get_logger(__name__)


class DeploymentPerformance:
    """A class to represent the performance of a deployment.

    Attributes:
    ----------
    benchmark_script : str
        The script used for benchmarking, default is "vllm".
    """

    def __init__(
        self,
        deployment_url: str,
        deployment_name: str,
        model: str,
        concurrency: int,
        input_tokens: Optional[int],
        output_tokens: Optional[int],
        # target performance metrics made optional for cloud model integration
        target_ttft: Optional[int] = None,
        target_e2e_latency: Optional[int] = None,
        target_throughput_per_user: Optional[int] = None,
        datasets: Optional[list[dict]] = None,
        error_threshold: float = 0.5,
        benchmark_id: Optional[UUID] = None,
        model_type: Optional[str] = None,
        num_prompts: Optional[int] = None,
    ):
        """Construct all the necessary attributes for the DeploymentPerformance object.

        Parameters
        ----------
        benchmark_script : str, optional
            The script used for benchmarking (default is "vllm").
        """
        if model_type == "embedding":
            self.benchmark_script = "budlatent"
        else:
            self.benchmark_script = "vllm"
        self.deployment_url = deployment_url
        self.deployment_name = deployment_name
        self.model = model
        self.target_ttft = target_ttft
        self.target_e2e_latency = target_e2e_latency
        self.target_throughput_per_user = target_throughput_per_user
        self.concurrency = concurrency
        self.input_tokens = input_tokens or 50
        self.output_tokens = output_tokens or 100
        self.datasets = datasets
        self.error_threshold = error_threshold
        self.benchmark_id = benchmark_id
        self.model_type = model_type
        self.num_prompts = num_prompts

    def _verify_target_performance(self, result: Dict):
        """Verify the performance of the deployment against the target performance."""
        if self.model_type == "embedding":
            return not (result["mean_e2el_ms"] > self.target_e2e_latency * (1 + self.error_threshold))
        return not (
            result["mean_ttft_ms"] > self.target_ttft * (1 + self.error_threshold)
            or result["mean_e2el_ms"] > self.target_e2e_latency * (1 + self.error_threshold)
            or result["output_throughput_per_user"] <= self.target_throughput_per_user * (1 - self.error_threshold)
        )

    def run_performance_test(self):
        """Run a performance test on a deployment by namespace.

        Returns:
        -------
        result
            The result of the performance test.
        """
        logger.debug(f"Chosen dataset names: {self.datasets}")
        try:
            result = benchmark_tools.run_benchmark(
                self.deployment_name,
                self.deployment_url + "/v1",
                self.input_tokens,
                self.output_tokens,
                self.concurrency,
                self.benchmark_script,
                tokenizer=self.model,
                endpoint="/completions",
                datasets=self.datasets,
                benchmark_id=self.benchmark_id,
                num_prompts=self.num_prompts,
            )
            print(f"Benchmark Result: {result}")
            benchmark_status = False
            performance_status = False
            if result["successful_requests"] > 0:
                benchmark_status = True
                performance_status = self._verify_target_performance(result) if self.target_ttft is not None else True

        except Exception as e:
            import traceback

            logger.error(traceback.format_exc())
            error_str = str(e)
            logger.error(f"Error in benchmark: {error_str}")
            formatted_error = format_litellm_error_message(error_str)
            performance_status = False
            result = formatted_error
            benchmark_status = False
        return {"result": result, "performance_status": performance_status, "benchmark_status": benchmark_status}
