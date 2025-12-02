"""
Tests for shared/dedicated GPU mode memory validation in DirectSearchOptimizer.

This test suite verifies that the DirectSearchOptimizer correctly handles memory
validation for both shared (time-slicing) and dedicated GPU modes:
- Shared mode: uses available memory = total × (1 - utilization%)
- Dedicated mode: uses total GPU memory
"""

import os
import pytest
from unittest.mock import Mock, patch

# Set minimal required environment variables before importing budsim
os.environ.setdefault("PSQL_HOST", "localhost")
os.environ.setdefault("PSQL_PORT", "5432")
os.environ.setdefault("PSQL_DB_NAME", "test_db")
os.environ.setdefault("MODEL_REGISTRY_DIR", "/tmp/models")  # nosec B108
os.environ.setdefault("BUD_CONNECT_URL", "http://localhost:8000")

from budsim.simulator.direct_search import DirectSearchOptimizer


@pytest.fixture
def base_device_config():
    """Base device configuration with 80GB GPU."""
    return {
        "type": "cuda",
        "mem_per_GPU_in_GB": 80.0,
        "available_count": 8,
        "max_devices_per_node": 8,
        "total_nodes_with_device": 1,
        "cluster_id": "test-cluster",
    }


@pytest.fixture
def mock_heuristic_calculator():
    """Mock HeuristicCalculator for memory validation."""
    with patch("budsim.simulator.direct_search.HeuristicCalculator") as mock_calc:
        # Create a mock instance
        mock_instance = Mock()
        mock_calc.return_value = mock_instance

        # Mock validate_memory_requirements to return validation based on memory_in_GB
        def validate_memory(model_params):
            memory_gb = model_params.get("memory_in_GB", 0)
            # Assume model needs 50GB for this test
            required_memory = 50.0
            fits = memory_gb >= required_memory
            return {
                "valid": fits,
                "total_memory_gb": required_memory,
                "available_memory_gb": memory_gb,
                "message": f"Fits: {fits}" if fits else "Insufficient memory",
            }

        mock_instance.validate_memory_requirements = Mock(side_effect=validate_memory)
        yield mock_calc


def test_shared_mode_high_utilization_rejects(base_device_config, mock_heuristic_calculator):
    """Test that shared mode with 94% utilization correctly rejects deployment.

    With 80GB total and 94% utilization:
    - Available memory = 80 × (1 - 0.94) = 4.8GB
    - Model needs 50GB
    - Should reject
    """
    # Add shared mode with high utilization
    device_config = {
        **base_device_config,
        "hardware_mode": "time-slicing",
        "memory_utilization_percent": 94.345,
    }

    optimizer = DirectSearchOptimizer(
        model="test-model",
        input_tokens=512,
        output_tokens=512,
        max_concurrency=20,
        target_ttft=0.1,
        target_throughput_per_user=10.0,
        target_e2e_latency=1.0,
        device_config=device_config,
        engine_name="vllm",
        use_heuristic=True,
        supports_lora=False,
    )

    # Check memory requirements
    fits, _ = optimizer._check_memory_requirements(tp_size=1, pp_size=1, concurrency=1)

    # Should NOT fit because available memory (4.8GB) < required (50GB)
    assert not fits, "Configuration should be rejected due to insufficient available memory in shared mode"


def test_shared_mode_low_utilization_accepts(base_device_config, mock_heuristic_calculator):
    """Test that shared mode with 10% utilization accepts deployment if memory fits.

    With 80GB total and 10% utilization:
    - Available memory = 80 × (1 - 0.10) = 72GB
    - Model needs 50GB
    - Should accept
    """
    # Add shared mode with low utilization
    device_config = {
        **base_device_config,
        "hardware_mode": "shared",
        "memory_utilization_percent": 10.0,
    }

    optimizer = DirectSearchOptimizer(
        model="test-model",
        input_tokens=512,
        output_tokens=512,
        max_concurrency=20,
        target_ttft=0.1,
        target_throughput_per_user=10.0,
        target_e2e_latency=1.0,
        device_config=device_config,
        engine_name="vllm",
        use_heuristic=True,
        supports_lora=False,
    )

    # Check memory requirements
    fits, _ = optimizer._check_memory_requirements(tp_size=1, pp_size=1, concurrency=1)

    # Should fit because available memory (72GB) >= required (50GB)
    assert fits, "Configuration should be accepted with sufficient available memory in shared mode"


def test_dedicated_mode_ignores_utilization(base_device_config, mock_heuristic_calculator):
    """Test that dedicated mode uses total memory regardless of utilization.

    With 80GB total and 94% utilization (dedicated mode):
    - Available memory = 80GB (ignores utilization)
    - Model needs 50GB
    - Should accept
    """
    # Add dedicated mode with high utilization (should be ignored)
    device_config = {
        **base_device_config,
        "hardware_mode": "dedicated",
        "memory_utilization_percent": 94.345,
    }

    optimizer = DirectSearchOptimizer(
        model="test-model",
        input_tokens=512,
        output_tokens=512,
        max_concurrency=20,
        target_ttft=0.1,
        target_throughput_per_user=10.0,
        target_e2e_latency=1.0,
        device_config=device_config,
        engine_name="vllm",
        use_heuristic=True,
        supports_lora=False,
    )

    # Check memory requirements
    fits, _ = optimizer._check_memory_requirements(tp_size=1, pp_size=1, concurrency=1)

    # Should fit because dedicated mode uses total memory (80GB) >= required (50GB)
    assert fits, "Configuration should be accepted in dedicated mode using total memory"


def test_no_hardware_mode_defaults_to_dedicated(base_device_config, mock_heuristic_calculator):
    """Test that missing hardware_mode defaults to dedicated behavior.

    With 80GB total and no hardware_mode specified:
    - Should default to dedicated mode
    - Available memory = 80GB (ignores any utilization)
    - Model needs 50GB
    - Should accept
    """
    # No hardware_mode field - should default to dedicated
    device_config = base_device_config.copy()
    # Even with high utilization, should be ignored
    device_config["memory_utilization_percent"] = 94.0

    optimizer = DirectSearchOptimizer(
        model="test-model",
        input_tokens=512,
        output_tokens=512,
        max_concurrency=20,
        target_ttft=0.1,
        target_throughput_per_user=10.0,
        target_e2e_latency=1.0,
        device_config=device_config,
        engine_name="vllm",
        use_heuristic=True,
        supports_lora=False,
    )

    # Check memory requirements
    fits, _ = optimizer._check_memory_requirements(tp_size=1, pp_size=1, concurrency=1)

    # Should fit because defaults to dedicated mode with total memory
    assert fits, "Configuration should be accepted when hardware_mode not specified (defaults to dedicated)"


def test_shared_mode_zero_utilization_uses_total(base_device_config, mock_heuristic_calculator):
    """Test that shared mode with 0% utilization uses total memory.

    Edge case: shared mode but 0% utilization
    - Available memory = 80 × (1 - 0.0) = 80GB
    - Model needs 50GB
    - Should accept
    """
    device_config = {
        **base_device_config,
        "hardware_mode": "shared",
        "memory_utilization_percent": 0.0,
    }

    optimizer = DirectSearchOptimizer(
        model="test-model",
        input_tokens=512,
        output_tokens=512,
        max_concurrency=20,
        target_ttft=0.1,
        target_throughput_per_user=10.0,
        target_e2e_latency=1.0,
        device_config=device_config,
        engine_name="vllm",
        use_heuristic=True,
        supports_lora=False,
    )

    # Check memory requirements
    fits, _ = optimizer._check_memory_requirements(tp_size=1, pp_size=1, concurrency=1)

    # Should fit with full memory available
    assert fits, "Configuration should be accepted in shared mode with 0% utilization"


def test_shared_mode_pre_reduced_memory_avoids_double_reduction(base_device_config, mock_heuristic_calculator):
    """Test that when memory was already reduced upstream, we don't reduce again.

    This tests the fix for the double memory reduction bug:
    - Total GPU memory: 80GB
    - Already allocated: 24GB
    - Available memory (pre-reduced by workflows.py): 56GB
    - mem_per_GPU_in_GB is set to 56GB (not 80GB)
    - total_memory_gb_original is set to 80GB (marker that memory was pre-reduced)
    - memory_utilization_percent: 30% (should be IGNORED because memory was already reduced)
    - Model needs 50GB
    - Should accept (56GB >= 50GB), NOT incorrectly reject (56 * 0.7 = 39.2GB < 50GB)
    """
    # Simulate what workflows.py does: reduce memory and set marker
    device_config = {
        **base_device_config,
        "hardware_mode": "shared",
        "mem_per_GPU_in_GB": 56.0,  # Already reduced: 80 - 24 = 56GB
        "total_memory_gb_original": 80.0,  # Marker that memory was pre-reduced
        "memory_allocated_gb": 24.0,  # For reference
        "memory_utilization_percent": 30.0,  # Should be IGNORED
    }

    optimizer = DirectSearchOptimizer(
        model="test-model",
        input_tokens=512,
        output_tokens=512,
        max_concurrency=20,
        target_ttft=0.1,
        target_throughput_per_user=10.0,
        target_e2e_latency=1.0,
        device_config=device_config,
        engine_name="vllm",
        use_heuristic=True,
        supports_lora=False,
    )

    # Check memory requirements
    fits, _ = optimizer._check_memory_requirements(tp_size=1, pp_size=1, concurrency=1)

    # Should fit because:
    # - total_memory_gb_original is set, so we skip utilization calculation
    # - Available memory = 56GB (pre-reduced)
    # - Model needs 50GB
    # - 56GB >= 50GB → fits
    # Without the fix, it would incorrectly calculate: 56 * 0.7 = 39.2GB < 50GB → doesn't fit
    assert fits, (
        "Configuration should be accepted when memory was pre-reduced upstream. "
        "The double reduction bug would incorrectly reject this."
    )


def test_shared_mode_without_marker_applies_utilization(base_device_config, mock_heuristic_calculator):
    """Test legacy path: when total_memory_gb_original is NOT set, apply utilization.

    This ensures backward compatibility for cases where workflows.py didn't pre-reduce memory.
    - Total GPU memory: 80GB
    - No total_memory_gb_original marker
    - memory_utilization_percent: 50%
    - Available = 80 * 0.5 = 40GB
    - Model needs 50GB
    - Should reject
    """
    device_config = {
        **base_device_config,
        "hardware_mode": "shared",
        "mem_per_GPU_in_GB": 80.0,  # Not pre-reduced
        # NO total_memory_gb_original - marker is absent
        "memory_utilization_percent": 50.0,
    }

    optimizer = DirectSearchOptimizer(
        model="test-model",
        input_tokens=512,
        output_tokens=512,
        max_concurrency=20,
        target_ttft=0.1,
        target_throughput_per_user=10.0,
        target_e2e_latency=1.0,
        device_config=device_config,
        engine_name="vllm",
        use_heuristic=True,
        supports_lora=False,
    )

    # Check memory requirements
    fits, _ = optimizer._check_memory_requirements(tp_size=1, pp_size=1, concurrency=1)

    # Should NOT fit because:
    # - No marker, so utilization calculation is applied
    # - Available memory = 80 * 0.5 = 40GB
    # - Model needs 50GB
    # - 40GB < 50GB → doesn't fit
    assert not fits, (
        "Configuration should be rejected when utilization calculation is applied (legacy path)"
    )
