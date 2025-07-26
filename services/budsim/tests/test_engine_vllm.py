from typing import Dict, Any
import pytest
from budsim.engine_ops.vllm import EngineCompatibility

@pytest.mark.parametrize("model_name, expected_compatibility", [
    ("Qwen/Qwen2-0.5B-Instruct", True),
    ("meta-llama/Meta-Llama-3.1-8B-Instruct", True),
    ("openai/whisper-large-v3-turbo", False),
])
def test_model_compatibility(model_name: str, expected_compatibility: bool) -> None:
    engine_compatibility = EngineCompatibility()
    assert engine_compatibility.check_model_compatibility(model_name) == expected_compatibility


# @pytest.mark.parametrize("engine_args, expected_compatibility", [
#     ({"block_size": 16, "enable_chunked_prefill": False, "enable_prefix_caching": False, "num_scheduler_steps": 1, "enforce_eager": True, "max_context_len_to_capture": None, "attention_backend": "TORCH_SDPA", "target_device": "cpu"}, True),
#     ({"block_size": 16, "enable_chunked_prefill": True, "enable_prefix_caching": True, "num_scheduler_steps": 2, "enforce_eager": False, "max_context_len_to_capture": 1000, "attention_backend": "TORCH_SDPA", "target_device": "cpu"}, False),
# ])
# def test_engine_args_compatibility(engine_args: Dict[str, Any], expected_compatibility: bool) -> None:
#     engine_compatibility = EngineCompatibility()
#     assert engine_compatibility.check_args_compatibility(engine_args) == expected_compatibility
