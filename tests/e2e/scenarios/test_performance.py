"""E2E performance tests for inference API."""

import time
import pytest
import logging
import statistics
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

from tests.e2e.utils import make_inference_request, batch_inference

logger = logging.getLogger(__name__)


@pytest.mark.performance
@pytest.mark.slow
class TestLatency:
    """Test latency characteristics of the inference API."""
    
    def test_simple_request_latency(self, budproxy_client, test_models):
        """Test latency for simple single requests."""
        model = test_models["small"]
        latencies = []
        
        # Warm up
        budproxy_client.inference(
            model=model,
            prompt="Warm up request",
            max_tokens=10
        )
        
        # Measure latencies
        for i in range(10):
            start_time = time.time()
            
            result = budproxy_client.inference(
                model=model,
                prompt=f"Simple test {i}",
                max_tokens=50
            )
            
            latency = (time.time() - start_time) * 1000  # Convert to ms
            latencies.append(latency)
            
            assert result is not None, f"Request {i} failed"
        
        # Calculate statistics
        avg_latency = statistics.mean(latencies)
        p95_latency = statistics.quantiles(latencies, n=20)[18]  # 95th percentile
        p99_latency = statistics.quantiles(latencies, n=100)[98]  # 99th percentile
        
        logger.info(f"Latency stats - Avg: {avg_latency:.0f}ms, P95: {p95_latency:.0f}ms, P99: {p99_latency:.0f}ms")
        
        # Assert reasonable latencies (adjust based on your SLA)
        assert avg_latency < 2000, f"Average latency too high: {avg_latency}ms"
        assert p95_latency < 5000, f"P95 latency too high: {p95_latency}ms"
    
    def test_cold_start_latency(self, budproxy_client, test_models):
        """Test cold start latency characteristics."""
        model = test_models["small"]
        
        # Wait to ensure any caches are cold
        time.sleep(30)
        
        # Measure cold start
        start_time = time.time()
        result = budproxy_client.inference(
            model=model,
            prompt="Cold start test",
            max_tokens=50
        )
        cold_latency = (time.time() - start_time) * 1000
        
        assert result is not None
        logger.info(f"Cold start latency: {cold_latency:.0f}ms")
        
        # Measure warm request
        start_time = time.time()
        result = budproxy_client.inference(
            model=model,
            prompt="Warm request test",
            max_tokens=50
        )
        warm_latency = (time.time() - start_time) * 1000
        
        logger.info(f"Warm request latency: {warm_latency:.0f}ms")
        logger.info(f"Cold start overhead: {cold_latency - warm_latency:.0f}ms")
        
        # Cold start should be within reasonable bounds
        assert cold_latency < 10000, f"Cold start too slow: {cold_latency}ms"


@pytest.mark.performance
@pytest.mark.slow
class TestThroughput:
    """Test throughput characteristics."""
    
    def test_sequential_throughput(self, budproxy_client, test_models):
        """Test throughput with sequential requests."""
        model = test_models["small"]
        num_requests = 20
        
        start_time = time.time()
        successful = 0
        
        for i in range(num_requests):
            try:
                result = budproxy_client.inference(
                    model=model,
                    prompt=f"Throughput test {i}",
                    max_tokens=50,
                    timeout=30
                )
                if result:
                    successful += 1
            except Exception as e:
                logger.error(f"Request {i} failed: {e}")
        
        duration = time.time() - start_time
        throughput = successful / duration
        
        logger.info(f"Sequential throughput: {throughput:.2f} req/s")
        logger.info(f"Success rate: {successful}/{num_requests}")
        
        assert successful >= num_requests * 0.95, "Too many failed requests"
        assert throughput > 0.5, f"Throughput too low: {throughput:.2f} req/s"
    
    def test_concurrent_throughput(self, budproxy_client, test_models):
        """Test throughput with concurrent requests."""
        model = test_models["small"]
        num_requests = 50
        max_workers = 10
        
        prompts = [f"Concurrent test {i}" for i in range(num_requests)]
        
        start_time = time.time()
        results = batch_inference(
            budproxy_client.base_url,
            model,
            prompts,
            max_tokens=50,
            max_workers=max_workers,
            timeout=30
        )
        duration = time.time() - start_time
        
        successful = sum(1 for r in results if r.success)
        throughput = successful / duration
        
        logger.info(f"Concurrent throughput: {throughput:.2f} req/s")
        logger.info(f"Success rate: {successful}/{num_requests}")
        logger.info(f"Duration: {duration:.2f}s")
        
        assert successful >= num_requests * 0.9, "Too many failed requests"
        assert throughput > 2.0, f"Concurrent throughput too low: {throughput:.2f} req/s"


@pytest.mark.performance
@pytest.mark.load
class TestScalability:
    """Test system scalability."""
    
    def test_increasing_load(self, budproxy_client, test_models):
        """Test system behavior under increasing load."""
        model = test_models["small"]
        load_stages = [1, 5, 10, 20, 30]  # Concurrent users
        
        results = {}
        
        for concurrent_users in load_stages:
            logger.info(f"Testing with {concurrent_users} concurrent users")
            
            # Generate requests
            num_requests = concurrent_users * 5
            prompts = [f"Load test {i}" for i in range(num_requests)]
            
            start_time = time.time()
            batch_results = batch_inference(
                budproxy_client.base_url,
                model,
                prompts,
                max_tokens=50,
                max_workers=concurrent_users,
                timeout=30
            )
            duration = time.time() - start_time
            
            successful = sum(1 for r in batch_results if r.success)
            failed = num_requests - successful
            avg_latency = statistics.mean([r.latency for r in batch_results if r.success])
            
            results[concurrent_users] = {
                "duration": duration,
                "successful": successful,
                "failed": failed,
                "throughput": successful / duration,
                "avg_latency": avg_latency,
            }
            
            logger.info(f"  Throughput: {results[concurrent_users]['throughput']:.2f} req/s")
            logger.info(f"  Avg latency: {avg_latency:.0f}ms")
            logger.info(f"  Success rate: {successful}/{num_requests}")
            
            # Brief pause between stages
            time.sleep(5)
        
        # Analyze scalability
        throughputs = [results[cu]["throughput"] for cu in load_stages]
        max_throughput = max(throughputs)
        
        logger.info("\nScalability Summary:")
        for cu in load_stages:
            logger.info(f"  {cu} users: {results[cu]['throughput']:.2f} req/s")
        
        # System should scale somewhat linearly up to a point
        assert results[5]["throughput"] > results[1]["throughput"] * 3, \
            "System doesn't scale with increased load"
        
        # Latency shouldn't degrade too much
        assert results[20]["avg_latency"] < results[1]["avg_latency"] * 5, \
            "Latency degrades too much under load"


@pytest.mark.performance
class TestResourceEfficiency:
    """Test resource utilization efficiency."""
    
    def test_tokens_per_second(self, budproxy_client, test_models):
        """Test token generation rate."""
        model = test_models["small"]
        
        # Test with different output lengths
        token_counts = [50, 100, 200, 500]
        results = []
        
        for max_tokens in token_counts:
            start_time = time.time()
            
            response = budproxy_client.inference_raw(
                model=model,
                prompt="Generate a detailed explanation about artificial intelligence",
                max_tokens=max_tokens
            )
            
            duration = time.time() - start_time
            
            if response and "usage" in response:
                tokens_generated = response["usage"].get("completion_tokens", 0)
                tokens_per_second = tokens_generated / duration if duration > 0 else 0
                
                results.append({
                    "requested": max_tokens,
                    "generated": tokens_generated,
                    "duration": duration,
                    "tokens_per_second": tokens_per_second,
                })
                
                logger.info(f"Tokens: {tokens_generated}, Time: {duration:.2f}s, "
                           f"Rate: {tokens_per_second:.1f} tokens/s")
        
        # Calculate average token rate
        if results:
            avg_rate = statistics.mean([r["tokens_per_second"] for r in results])
            logger.info(f"Average token generation rate: {avg_rate:.1f} tokens/s")
            
            # Assert minimum performance
            assert avg_rate > 10, f"Token generation too slow: {avg_rate:.1f} tokens/s"
    
    def test_batch_efficiency(self, budproxy_client, test_models):
        """Test efficiency of batch processing."""
        model = test_models["small"]
        
        # Single request baseline
        single_start = time.time()
        single_result = budproxy_client.inference(
            model=model,
            prompt="Single request test",
            max_tokens=100
        )
        single_duration = time.time() - single_start
        
        # Batch requests
        batch_size = 10
        batch_prompts = [f"Batch request {i}" for i in range(batch_size)]
        
        batch_start = time.time()
        batch_results = batch_inference(
            budproxy_client.base_url,
            model,
            batch_prompts,
            max_tokens=100,
            max_workers=batch_size,
            timeout=30
        )
        batch_duration = time.time() - batch_start
        
        successful = sum(1 for r in batch_results if r.success)
        
        # Calculate efficiency
        single_total_time = single_duration * batch_size  # If processed sequentially
        batch_efficiency = (single_total_time / batch_duration) * (successful / batch_size)
        
        logger.info(f"Single request time: {single_duration:.2f}s")
        logger.info(f"Batch time for {batch_size} requests: {batch_duration:.2f}s")
        logger.info(f"Batch efficiency: {batch_efficiency:.2f}x")
        logger.info(f"Time saved: {single_total_time - batch_duration:.2f}s")
        
        # Batch should be more efficient
        assert batch_efficiency > 1.5, f"Batch processing not efficient: {batch_efficiency:.2f}x"


@pytest.mark.performance
@pytest.mark.slow
@pytest.mark.parametrize("prompt_length", [10, 100, 500, 1000])
def test_prompt_length_impact(budproxy_client, test_models, prompt_length):
    """Test impact of prompt length on performance."""
    model = test_models["small"]
    
    # Generate prompt of specified length (words)
    prompt = " ".join([f"word{i}" for i in range(prompt_length)])
    
    latencies = []
    for i in range(5):
        start_time = time.time()
        
        result = budproxy_client.inference(
            model=model,
            prompt=prompt,
            max_tokens=50,
            timeout=60
        )
        
        latency = (time.time() - start_time) * 1000
        latencies.append(latency)
        
        assert result is not None
    
    avg_latency = statistics.mean(latencies)
    logger.info(f"Prompt length {prompt_length} words: Avg latency {avg_latency:.0f}ms")
    
    # Longer prompts should take more time, but not excessively
    if prompt_length <= 100:
        assert avg_latency < 3000, f"Latency too high for short prompt: {avg_latency}ms"
    else:
        assert avg_latency < 10000, f"Latency too high for long prompt: {avg_latency}ms"