from typing import Dict, Any
import pytest
from budsim.engine_ops.sglang import EngineCompatibility

@pytest.mark.parametrize("model_name, expected_compatibility", [
    ("Qwen/Qwen2-0.5B-Instruct", True),
    ("meta-llama/Meta-Llama-3.1-8B-Instruct", True),
    ("openai/whisper-large-v3-turbo", False),
    ("mosaicml/mpt-7b", False)
])
def test_model_compatibility(model_name: str, expected_compatibility: bool) -> None:
    engine_compatibility = EngineCompatibility()
    assert engine_compatibility.check_model_compatibility(model_name) == expected_compatibility