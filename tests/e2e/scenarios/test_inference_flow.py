"""E2E tests for inference flow through the complete pipeline."""

import time
import pytest
import logging
from typing import Dict, Any

from tests.e2e.utils import (
    make_inference_request,
    batch_inference,
    validate_response,
    measure_latency
)

logger = logging.getLogger(__name__)


@pytest.mark.smoke
class TestBasicInference:
    """Basic inference flow tests."""
    
    def test_health_check(self, budproxy_client):
        """Test BudProxy health endpoint."""
        assert budproxy_client.health(), "BudProxy health check failed"
    
    def test_simple_inference(self, budproxy_client, test_models):
        """Test simple inference request."""
        model = test_models["small"]
        prompt = "Hello, how are you?"
        
        result = budproxy_client.inference(
            model=model,
            prompt=prompt,
            max_tokens=50
        )
        
        assert result is not None, "No response received"
        assert "choices" in result, "Response missing choices"
        assert len(result["choices"]) > 0, "No choices in response"
        assert "text" in result["choices"][0], "No text in response"
        
        logger.info(f"Response: {result['choices'][0]['text'][:100]}...")
    
    def test_response_validation(self, budproxy_client, test_models):
        """Test response structure validation."""
        model = test_models["small"]
        prompt = "What is 2+2?"
        
        result = budproxy_client.inference(
            model=model,
            prompt=prompt,
            max_tokens=10
        )
        
        is_valid, errors = validate_response(result)
        assert is_valid, f"Response validation failed: {errors}"
        
        # Check specific fields
        assert "id" in result
        assert "object" in result
        assert "created" in result
        assert "model" in result
        assert result["model"] == model
        
        # Check usage stats
        assert "usage" in result
        assert result["usage"]["total_tokens"] > 0


@pytest.mark.integration
class TestEndToEndInference:
    """End-to-end inference tests across clusters."""
    
    def test_cross_cluster_inference(self, budproxy_client, test_models, test_prompts):
        """Test inference request flowing through multiple clusters."""
        model = test_models.get("llama2", test_models["small"])
        
        for prompt in test_prompts[:3]:  # Test first 3 prompts
            logger.info(f"Testing prompt: {prompt}")
            
            result = budproxy_client.inference(
                model=model,
                prompt=prompt,
                max_tokens=100,
                temperature=0.7
            )
            
            assert result is not None
            assert "choices" in result
            assert len(result["choices"][0]["text"]) > 0
            
            # Verify the response makes sense
            response_text = result["choices"][0]["text"]
            assert len(response_text.split()) > 5, "Response too short"
    
    @pytest.mark.parametrize("model_key", ["small", "llama2", "mistral"])
    def test_multiple_models(self, budproxy_client, test_models, model_key):
        """Test inference with different models."""
        if model_key not in test_models:
            pytest.skip(f"Model {model_key} not configured")
        
        model = test_models[model_key]
        prompt = "Explain quantum computing in one sentence."
        
        try:
            result = budproxy_client.inference(
                model=model,
                prompt=prompt,
                max_tokens=50
            )
            
            assert result is not None
            assert "choices" in result
            logger.info(f"Model {model} response: {result['choices'][0]['text']}")
        
        except Exception as e:
            if "not found" in str(e).lower():
                pytest.skip(f"Model {model} not deployed")
            raise
    
    def test_streaming_inference(self, budproxy_client, test_models):
        """Test streaming inference if supported."""
        model = test_models["small"]
        prompt = "Count from 1 to 10 slowly."
        
        # Note: This test assumes streaming support
        # Actual implementation would depend on the API
        try:
            result = budproxy_client.inference(
                model=model,
                prompt=prompt,
                max_tokens=100,
                stream=True  # Enable streaming
            )
            
            if isinstance(result, dict) and "choices" in result:
                # Non-streaming response, skip test
                pytest.skip("Streaming not supported")
            
            # Process streaming response
            chunks = []
            for chunk in result:
                chunks.append(chunk)
            
            assert len(chunks) > 1, "Expected multiple chunks for streaming"
        
        except Exception as e:
            if "stream" in str(e).lower():
                pytest.skip("Streaming not supported")
            raise


@pytest.mark.slow
class TestInferenceLatency:
    """Latency and performance tests."""
    
    def test_latency_single_request(self, budproxy_client, test_models):
        """Test single request latency."""
        model = test_models["small"]
        prompt = "Hello!"
        
        def inference_func():
            return make_inference_request(
                budproxy_client.base_url,
                model,
                prompt,
                max_tokens=20
            )
        
        latency_stats = measure_latency(inference_func, iterations=10)
        
        logger.info(f"Latency statistics: {latency_stats}")
        
        # Check against thresholds
        assert latency_stats["median"] < 5000, "Median latency too high (>5s)"
        assert latency_stats["p95"] < 10000, "P95 latency too high (>10s)"
    
    def test_batch_inference_latency(self, budproxy_client, test_models, test_prompts):
        """Test batch inference latency."""
        model = test_models["small"]
        prompts = test_prompts[:5]
        
        start_time = time.time()
        results = batch_inference(
            budproxy_client.base_url,
            model,
            prompts,
            max_tokens=50,
            max_workers=5
        )
        total_time = time.time() - start_time
        
        # Analyze results
        successful = sum(1 for r in results if r.success)
        failed = sum(1 for r in results if not r.success)
        latencies = [r.latency_ms for r in results if r.success]
        
        logger.info(f"Batch inference completed in {total_time:.2f}s")
        logger.info(f"Successful: {successful}, Failed: {failed}")
        
        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            logger.info(f"Average latency: {avg_latency:.2f}ms")
            
            assert successful > len(prompts) * 0.9, "Too many failed requests"
            assert avg_latency < 5000, "Average latency too high"
    
    @pytest.mark.parametrize("prompt_length", ["short", "medium", "long"])
    def test_prompt_length_impact(self, budproxy_client, test_models, prompt_length):
        """Test how prompt length affects latency."""
        from tests.e2e.utils import generate_test_prompt
        
        model = test_models["small"]
        prompt = generate_test_prompt("general", prompt_length)
        
        # Measure latency for different prompt lengths
        result = make_inference_request(
            budproxy_client.base_url,
            model,
            prompt,
            max_tokens=100
        )
        
        logger.info(f"Prompt length: {prompt_length}, "
                   f"Latency: {result.latency_ms:.2f}ms")
        
        # Longer prompts should still complete in reasonable time
        assert result.success, f"Request failed for {prompt_length} prompt"
        assert result.latency_ms < 15000, f"Latency too high for {prompt_length} prompt"


@pytest.mark.integration
class TestAdvancedInference:
    """Advanced inference scenarios."""
    
    def test_context_window(self, budproxy_client, test_models):
        """Test handling of context window limits."""
        model = test_models.get("llama2", test_models["small"])
        
        # Create a very long prompt
        long_prompt = "Please summarize the following text: " + " ".join([
            "This is a test sentence." for _ in range(500)
        ])
        
        try:
            result = budproxy_client.inference(
                model=model,
                prompt=long_prompt,
                max_tokens=100
            )
            
            assert result is not None
            assert "choices" in result
            
        except Exception as e:
            # Check if it's a context length error
            error_msg = str(e).lower()
            if "context" in error_msg or "length" in error_msg or "token" in error_msg:
                logger.info("Context window limit reached as expected")
            else:
                raise
    
    def test_special_characters(self, budproxy_client, test_models):
        """Test handling of special characters in prompts."""
        model = test_models["small"]
        
        special_prompts = [
            "Test with emoji: 😀 🚀 🔥",
            "Test with unicode: ñáéíóú αβγδε",
            'Test with quotes: "Hello" \'World\'',
            "Test with newlines:\nLine 1\nLine 2",
            "Test with code: ```python\nprint('hello')\n```"
        ]
        
        for prompt in special_prompts:
            logger.info(f"Testing special prompt: {prompt[:50]}...")
            
            result = budproxy_client.inference(
                model=model,
                prompt=prompt,
                max_tokens=50
            )
            
            assert result is not None
            assert "choices" in result
            assert len(result["choices"][0]["text"]) > 0
    
    def test_concurrent_inference(self, budproxy_client, test_models, test_prompts):
        """Test concurrent inference requests."""
        import asyncio
        from tests.e2e.utils import async_batch_inference
        
        model = test_models["small"]
        prompts = test_prompts[:10]  # Use 10 prompts
        
        # Run async batch inference
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            results = loop.run_until_complete(
                async_batch_inference(
                    budproxy_client.base_url,
                    model,
                    prompts,
                    max_concurrent=5
                )
            )
            
            successful = sum(1 for r in results if r.success)
            logger.info(f"Concurrent requests: {successful}/{len(prompts)} successful")
            
            assert successful >= len(prompts) * 0.8, "Too many concurrent request failures"
            
        finally:
            loop.close()
    
    def test_model_switching(self, budproxy_client, test_models):
        """Test rapid switching between models."""
        models = [test_models["small"]]
        if "llama2" in test_models:
            models.append(test_models["llama2"])
        
        prompt = "What is artificial intelligence?"
        
        for i in range(5):
            model = models[i % len(models)]
            logger.info(f"Request {i+1} using model: {model}")
            
            result = budproxy_client.inference(
                model=model,
                prompt=prompt,
                max_tokens=50
            )
            
            assert result is not None
            assert result["model"] == model
            
            # Small delay between switches
            time.sleep(0.5)