"""Unit tests for LoRA memory optimization functionality."""

from unittest.mock import patch

import pytest

from budsim.simulator.direct_search import DirectSearchOptimizer
from budsim.simulator.heuristic import HeuristicCalculator


class TestHeuristicCalculatorLoRA:
    """Test LoRA memory optimization in HeuristicCalculator."""

    @pytest.fixture
    def calculator(self):
        """Create HeuristicCalculator instance."""
        return HeuristicCalculator()

    @pytest.fixture
    def model_params(self):
        """Create sample model parameters."""
        return {
            "model": "meta-llama/Llama-2-7b-hf",
            "mean_input_tokens": 512,
            "mean_output_tokens": 256,
            "concurrent_requests": 4,
            "tensor_parallel_size": 1,
            "pipeline_parallel_size": 1,
            "memory_in_GB": 40.0,
            "quantization_bits": 16,
        }

    def test_validate_memory_requirements_without_lora(self, calculator, model_params):
        """Test memory validation without LoRA parameters."""
        result = calculator.validate_memory_requirements(model_params)

        assert "valid" in result
        assert "total_memory_gb" in result
        assert "available_memory_gb" in result
        assert "breakdown" in result
        assert result["available_memory_gb"] == 40.0

    def test_validate_memory_requirements_with_lora(self, calculator, model_params):
        """Test memory validation with LoRA parameters."""
        result = calculator.validate_memory_requirements(
            model_params, max_loras=3, max_lora_rank=256
        )

        assert "valid" in result
        assert "total_memory_gb" in result
        # Note: Memory should be higher with LoRA adapters
        # This can be verified by comparing with result without LoRA if needed

    def test_find_optimal_max_loras_all_fit(self, calculator, model_params):
        """Test finding optimal max_loras when all values fit."""
        with patch.object(calculator, "validate_memory_requirements") as mock_validate:
            # Mock that all configurations fit
            mock_validate.return_value = {"valid": True, "total_memory_gb": 30.0, "available_memory_gb": 40.0}

            optimal = calculator.find_optimal_max_loras(model_params)

            assert optimal == 5  # Should return initial_max_loras

    def test_find_optimal_max_loras_binary_search(self, calculator, model_params):
        """Test binary search for optimal max_loras."""
        with patch.object(calculator, "validate_memory_requirements") as mock_validate:
            # Mock: 5 doesn't fit, but 1-3 do fit
            def validate_side_effect(model_params, max_loras=None, max_lora_rank=256):
                if max_loras is None:
                    return {"valid": True, "total_memory_gb": 30.0, "available_memory_gb": 40.0}
                valid = max_loras <= 3
                memory = 35.0 + (max_loras * 2)  # Simulate memory increasing with LoRAs
                return {"valid": valid, "total_memory_gb": memory, "available_memory_gb": 40.0}

            mock_validate.side_effect = validate_side_effect

            optimal = calculator.find_optimal_max_loras(model_params, initial_max_loras=5)

            assert optimal == 3  # Should find max_loras=3 as optimal

    def test_find_optimal_max_loras_min_doesnt_fit(self, calculator, model_params):
        """Test when even minimum max_loras doesn't fit."""
        with patch.object(calculator, "validate_memory_requirements") as mock_validate:
            # Mock that nothing fits
            mock_validate.return_value = {"valid": False, "total_memory_gb": 50.0, "available_memory_gb": 40.0}

            optimal = calculator.find_optimal_max_loras(model_params)

            assert optimal is None  # Should return None

    def test_find_optimal_max_loras_only_one_fits(self, calculator, model_params):
        """Test when only min_max_loras=1 fits."""
        with patch.object(calculator, "validate_memory_requirements") as mock_validate:
            def validate_side_effect(model_params, max_loras=None, max_lora_rank=256):
                if max_loras is None:
                    return {"valid": True, "total_memory_gb": 30.0, "available_memory_gb": 40.0}
                valid = max_loras == 1
                memory = 38.0 + (max_loras * 3)  # Only 1 fits
                return {"valid": valid, "total_memory_gb": memory, "available_memory_gb": 40.0}

            mock_validate.side_effect = validate_side_effect

            optimal = calculator.find_optimal_max_loras(model_params)

            assert optimal == 1  # Should return minimum


class TestDirectSearchOptimizerLoRA:
    """Test LoRA optimization in DirectSearchOptimizer."""

    @pytest.fixture
    def optimizer_config(self):
        """Create optimizer configuration."""
        return {
            "model": "meta-llama/Llama-2-7b-hf",
            "input_tokens": 512,
            "output_tokens": 256,
            "max_concurrency": 8,
            "target_ttft": 0.5,
            "target_throughput_per_user": 50.0,
            "target_e2e_latency": 10.0,
            "engine_name": "vllm",
            "device_config": {
                "device_type": "cuda",
                "mem_per_GPU_in_GB": 40.0,
                "max_devices_per_node": 8,
                "total_nodes_with_device": 1,
                "total_devices": 8,
                "node_distribution": {},
            },
            "use_heuristic": True,
            "supports_lora": True,
        }

    def test_check_memory_requirements_with_lora(self, optimizer_config):
        """Test memory check with LoRA support enabled."""
        optimizer = DirectSearchOptimizer(**optimizer_config)

        with patch.object(optimizer._heuristic_calc, "find_optimal_max_loras") as mock_find, patch.object(
            optimizer._heuristic_calc, "validate_memory_requirements"
        ) as mock_validate:
            mock_find.return_value = 3
            # Mock validate_memory_requirements which is called after finding optimal max_loras
            # to store the validation result for memory values in shared mode
            mock_validate.return_value = {
                "valid": True,
                "total_memory_gb": 30.0,
                "available_memory_gb": 40.0,
                "breakdown": {"weights": 25.0, "kv_cache": 3.0, "activations": 2.0},
                "message": "OK",
            }

            fits, optimal_max_loras = optimizer._check_memory_requirements(tp_size=1, pp_size=1, concurrency=4)

            assert fits is True
            assert optimal_max_loras == 3
            mock_find.assert_called_once()
            # validate_memory_requirements should be called to store memory info for shared mode
            mock_validate.assert_called_once()

    def test_check_memory_requirements_without_lora(self, optimizer_config):
        """Test memory check without LoRA support."""
        optimizer_config["supports_lora"] = False
        optimizer = DirectSearchOptimizer(**optimizer_config)

        with patch.object(optimizer._heuristic_calc, "validate_memory_requirements") as mock_validate:
            mock_validate.return_value = {"valid": True, "total_memory_gb": 30.0, "available_memory_gb": 40.0}

            fits, optimal_max_loras = optimizer._check_memory_requirements(tp_size=1, pp_size=1, concurrency=4)

            assert fits is True
            assert optimal_max_loras is None
            mock_validate.assert_called_once()

    def test_check_memory_requirements_lora_doesnt_fit(self, optimizer_config):
        """Test memory check when LoRA configuration doesn't fit."""
        optimizer = DirectSearchOptimizer(**optimizer_config)

        with patch.object(optimizer._heuristic_calc, "find_optimal_max_loras") as mock_find:
            mock_find.return_value = None  # Even min doesn't fit

            fits, optimal_max_loras = optimizer._check_memory_requirements(tp_size=1, pp_size=1, concurrency=4)

            assert fits is False
            assert optimal_max_loras is None

    def test_check_memory_requirements_stores_validation_result_for_lora(self, optimizer_config):
        """Test that _last_validation_result is populated for LoRA configs.

        This is critical for shared mode to have access to memory values
        (total_memory, weight_memory, kv_cache_memory) in the final result.
        """
        optimizer = DirectSearchOptimizer(**optimizer_config)
        validation_result = {
            "valid": True,
            "total_memory_gb": 28.5,
            "available_memory_gb": 40.0,
            "breakdown": {"weights": 22.0, "kv_cache": 4.5, "activations": 2.0},
            "message": "OK",
        }

        with patch.object(optimizer._heuristic_calc, "find_optimal_max_loras") as mock_find, patch.object(
            optimizer._heuristic_calc, "validate_memory_requirements"
        ) as mock_validate:
            mock_find.return_value = 3
            mock_validate.return_value = validation_result

            fits, optimal_max_loras = optimizer._check_memory_requirements(tp_size=1, pp_size=1, concurrency=4)

            assert fits is True
            assert optimal_max_loras == 3
            # Verify _last_validation_result is populated for shared mode
            assert hasattr(optimizer, "_last_validation_result")
            assert optimizer._last_validation_result is not None
            assert optimizer._last_validation_result["total_memory_gb"] == 28.5
            assert optimizer._last_validation_result["breakdown"]["weights"] == 22.0
            assert optimizer._last_validation_result["breakdown"]["kv_cache"] == 4.5

    def test_max_loras_cached_in_validate_config(self, optimizer_config):
        """Test that optimal max_loras is cached during validation."""
        optimizer = DirectSearchOptimizer(**optimizer_config)

        with patch.object(optimizer._heuristic_calc, "find_optimal_max_loras") as mock_find:
            mock_find.return_value = 4

            result = optimizer._validate_config(tp_size=2, pp_size=1, concurrency=4)

            assert result is True
            cache_key = (2, 1, 4)
            assert cache_key in optimizer._max_loras_cache
            assert optimizer._max_loras_cache[cache_key] == 4

    def test_search_result_includes_max_loras(self, optimizer_config):
        """Test that SearchResult includes max_loras field."""
        optimizer = DirectSearchOptimizer(**optimizer_config)

        # Mock the necessary methods
        with patch.object(optimizer, "_validate_config", return_value=True), patch.object(
            optimizer, "heuristic_calculator", return_value=(100.0, 50.0, 5.0)
        ), patch.object(optimizer._heuristic_calc, "find_optimal_max_loras", return_value=3), patch(
            "budsim.simulator.direct_search.check_config_compatibility", return_value=True
        ):
            # Set up the cache
            optimizer._max_loras_cache[(1, 1, 4)] = 3

            result = optimizer._evaluate_config(tp_size=1, pp_size=1, concurrency=4)

            assert result is not None
            assert hasattr(result, "max_loras")
            assert result.max_loras == 3


class TestLoRAIntegration:
    """Integration tests for LoRA memory optimization."""

    def test_end_to_end_lora_optimization(self):
        """Test end-to-end LoRA optimization flow."""
        optimizer_config = {
            "model": "meta-llama/Llama-2-7b-hf",
            "input_tokens": 512,
            "output_tokens": 256,
            "max_concurrency": 8,
            "target_ttft": 0.5,
            "target_throughput_per_user": 50.0,
            "target_e2e_latency": 10.0,
            "engine_name": "vllm",
            "device_config": {
                "device_type": "cuda",
                "mem_per_GPU_in_GB": 40.0,
                "max_devices_per_node": 8,
                "total_nodes_with_device": 1,
                "total_devices": 8,
                "node_distribution": {},
            },
            "use_heuristic": True,
            "supports_lora": True,
        }

        optimizer = DirectSearchOptimizer(**optimizer_config)

        # Verify that LoRA support is enabled
        assert optimizer.supports_lora is True

        # Verify that max_loras cache is initialized
        assert hasattr(optimizer, "_max_loras_cache")
        assert isinstance(optimizer._max_loras_cache, dict)
