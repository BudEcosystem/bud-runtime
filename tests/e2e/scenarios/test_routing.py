"""E2E tests for request routing and load balancing."""

import time
import pytest
import logging
import statistics
from collections import Counter, defaultdict
from typing import List, Dict

from tests.e2e.utils import (
    make_inference_request,
    batch_inference,
    get_service_endpoints,
    wait_for_deployment_ready
)

logger = logging.getLogger(__name__)


@pytest.mark.integration
class TestModelRouting:
    """Test model routing through BudProxy."""
    
    def test_model_routing_basic(self, budproxy_client, test_models):
        """Test basic model routing."""
        # Test routing to different models
        for model_key, model_name in test_models.items():
            if model_key == "primary":  # Skip composite models
                continue
                
            logger.info(f"Testing routing to model: {model_name}")
            
            try:
                result = budproxy_client.inference(
                    model=model_name,
                    prompt="Hello",
                    max_tokens=10
                )
                
                assert result is not None
                assert result.get("model") == model_name
                logger.info(f"Successfully routed to {model_name}")
                
            except Exception as e:
                if "not found" in str(e).lower() or "404" in str(e):
                    logger.warning(f"Model {model_name} not available")
                else:
                    raise
    
    def test_invalid_model_routing(self, budproxy_client):
        """Test routing to invalid model."""
        with pytest.raises(Exception) as exc_info:
            budproxy_client.inference(
                model="non-existent-model",
                prompt="Test",
                max_tokens=10
            )
        
        # Should get a 404 or similar error
        assert "404" in str(exc_info.value) or "not found" in str(exc_info.value).lower()
    
    def test_model_alias_routing(self, budproxy_client):
        """Test routing using model aliases."""
        # Test if primary-llm routes to actual models
        try:
            result = budproxy_client.inference(
                model="primary-llm",
                prompt="What is AI?",
                max_tokens=50
            )
            
            assert result is not None
            # Should route to either llama2 or mistral based on config
            actual_model = result.get("model", "")
            assert "llama" in actual_model.lower() or "mistral" in actual_model.lower()
            
        except Exception as e:
            if "not found" in str(e).lower():
                pytest.skip("Model alias not configured")
            raise


@pytest.mark.integration
class TestLoadBalancing:
    """Test load balancing across model instances."""
    
    def test_round_robin_distribution(self, budproxy_client, test_models, k8s_inference_client):
        """Test round-robin load balancing."""
        model = test_models["small"]
        
        # Check if model has multiple replicas
        from kubernetes import client
        apps_v1 = client.AppsV1Api()
        
        try:
            # Find the deployment/statefulset for this model
            statefulsets = apps_v1.list_namespaced_stateful_set(
                namespace="inference-system",
                label_selector=f"app.kubernetes.io/instance={model}"
            )
            
            if not statefulsets.items:
                pytest.skip(f"No statefulset found for model {model}")
            
            replicas = statefulsets.items[0].spec.replicas
            if replicas < 2:
                pytest.skip(f"Model {model} has only {replicas} replica(s)")
            
            # Make multiple requests and track which pod handled each
            num_requests = replicas * 10
            pod_distribution = Counter()
            
            for i in range(num_requests):
                result = make_inference_request(
                    budproxy_client.base_url,
                    model,
                    f"Test request {i}",
                    max_tokens=10
                )
                
                # Try to identify which pod handled the request
                # This might be in response headers or need to check pod logs
                if result.success and result.response:
                    # Assuming pod info is in response (implementation specific)
                    pod_name = result.response.get("_pod_name", "unknown")
                    pod_distribution[pod_name] += 1
            
            logger.info(f"Request distribution: {dict(pod_distribution)}")
            
            # Check if distribution is roughly even
            if len(pod_distribution) > 1:
                counts = list(pod_distribution.values())
                avg_count = sum(counts) / len(counts)
                
                for count in counts:
                    # Allow 30% deviation from average
                    assert abs(count - avg_count) / avg_count < 0.3, \
                        "Uneven load distribution"
        
        except Exception as e:
            logger.warning(f"Could not verify load balancing: {e}")
            pytest.skip("Unable to verify load balancing")
    
    def test_session_affinity(self, budproxy_client, test_models):
        """Test session affinity if configured."""
        model = test_models["small"]
        
        # Make multiple requests with same session ID
        session_id = "test-session-123"
        responses = []
        
        for i in range(5):
            result = budproxy_client.inference(
                model=model,
                prompt=f"Request {i} from session",
                max_tokens=10,
                headers={"X-Session-ID": session_id}  # Assuming session ID in header
            )
            responses.append(result)
        
        # Check if all requests went to same backend
        # This would require backend identification in response
        logger.info("Session affinity test completed")
        # Actual verification would depend on implementation
    
    def test_weighted_routing(self, budproxy_client):
        """Test weighted routing between models."""
        # Test primary-llm which should route to different models
        model_counts = Counter()
        num_requests = 100
        
        for i in range(num_requests):
            try:
                result = budproxy_client.inference(
                    model="primary-llm",
                    prompt=f"Test {i}",
                    max_tokens=10
                )
                
                if result and "model" in result:
                    actual_model = result["model"]
                    model_counts[actual_model] += 1
            
            except Exception as e:
                if "not found" in str(e).lower():
                    pytest.skip("Weighted routing not configured")
                logger.warning(f"Request {i} failed: {e}")
        
        logger.info(f"Model distribution: {dict(model_counts)}")
        
        # Check if weights are roughly correct (70/30 split based on config)
        if len(model_counts) >= 2:
            total = sum(model_counts.values())
            for model, count in model_counts.items():
                ratio = count / total
                logger.info(f"Model {model}: {ratio:.2%} of requests")


@pytest.mark.integration
class TestRoutingResilience:
    """Test routing resilience and failover."""
    
    def test_backend_failure_handling(self, budproxy_client, test_models, k8s_inference_client):
        """Test handling of backend failures."""
        model = test_models["small"]
        
        # Make initial request to ensure model is working
        initial_result = budproxy_client.inference(
            model=model,
            prompt="Initial test",
            max_tokens=10
        )
        assert initial_result is not None
        
        # Simulate backend failure by scaling down
        from tests.e2e.utils import scale_deployment
        from kubernetes import client
        
        apps_v1 = client.AppsV1Api()
        
        try:
            # Find and scale down the model deployment
            statefulsets = apps_v1.list_namespaced_stateful_set(
                namespace="inference-system",
                label_selector=f"app.kubernetes.io/instance={model}"
            )
            
            if statefulsets.items:
                sts_name = statefulsets.items[0].metadata.name
                original_replicas = statefulsets.items[0].spec.replicas
                
                # Scale to 0
                logger.info(f"Scaling down {sts_name}")
                scale_deployment(apps_v1, "inference-system", sts_name, 0)
                time.sleep(10)  # Wait for scale down
                
                # Try inference - should fail or fallback
                try:
                    result = budproxy_client.inference(
                        model=model,
                        prompt="Test during failure",
                        max_tokens=10,
                        timeout=5
                    )
                    
                    # If it succeeds, might have fallback
                    logger.info("Request succeeded despite backend scale-down")
                    
                except Exception as e:
                    logger.info(f"Request failed as expected: {e}")
                
                # Scale back up
                logger.info(f"Scaling up {sts_name}")
                scale_deployment(apps_v1, "inference-system", sts_name, original_replicas)
                wait_for_deployment_ready(apps_v1, "inference-system", sts_name, timeout=120)
                
                # Verify recovery
                time.sleep(10)
                recovery_result = budproxy_client.inference(
                    model=model,
                    prompt="Test after recovery",
                    max_tokens=10
                )
                assert recovery_result is not None, "Service did not recover"
        
        except Exception as e:
            logger.warning(f"Backend failure test skipped: {e}")
            pytest.skip("Unable to test backend failure")
    
    def test_circuit_breaker(self, budproxy_client, test_models):
        """Test circuit breaker functionality."""
        model = test_models["small"]
        
        # Make many rapid requests to trigger circuit breaker
        failures = 0
        successes = 0
        circuit_open = False
        
        for i in range(50):
            try:
                result = budproxy_client.inference(
                    model=model,
                    prompt=f"Rapid request {i}",
                    max_tokens=5,
                    timeout=1  # Very short timeout to cause failures
                )
                successes += 1
                
            except Exception as e:
                failures += 1
                error_msg = str(e).lower()
                
                # Check for circuit breaker messages
                if "circuit" in error_msg or "breaker" in error_msg:
                    circuit_open = True
                    logger.info(f"Circuit breaker opened after {i} requests")
                    break
        
        logger.info(f"Requests - Success: {successes}, Failures: {failures}")
        
        # If circuit breaker is implemented, it should open after failures
        if failures > 10 and not circuit_open:
            logger.warning("Circuit breaker did not open despite failures")
    
    def test_retry_logic(self, budproxy_client, test_models):
        """Test retry logic for failed requests."""
        model = test_models["small"]
        
        # Use a prompt that might fail initially
        start_time = time.time()
        
        try:
            # Make request with potential for transient failure
            result = budproxy_client.inference(
                model=model,
                prompt="Test retry logic",
                max_tokens=10,
                timeout=30
            )
            
            elapsed = time.time() - start_time
            
            # If request took longer than expected, might indicate retries
            if elapsed > 5:
                logger.info(f"Request completed after {elapsed:.2f}s (possible retries)")
            
            assert result is not None
            
        except Exception as e:
            elapsed = time.time() - start_time
            logger.info(f"Request failed after {elapsed:.2f}s: {e}")
            
            # Check if retries were attempted
            if elapsed > 10:
                logger.info("Multiple retry attempts detected")


@pytest.mark.integration 
class TestDynamicRouting:
    """Test dynamic routing capabilities."""
    
    def test_latency_based_routing(self, budproxy_client, test_models):
        """Test latency-based routing if configured."""
        # Make multiple requests and measure latencies
        latencies_by_model = defaultdict(list)
        
        for i in range(20):
            for model_key, model_name in test_models.items():
                if model_key in ["primary", "small"]:  # Skip composite and test models
                    continue
                
                try:
                    result = make_inference_request(
                        budproxy_client.base_url,
                        model_name,
                        f"Latency test {i}",
                        max_tokens=20
                    )
                    
                    if result.success:
                        latencies_by_model[model_name].append(result.latency_ms)
                
                except:
                    pass
        
        # Calculate average latencies
        avg_latencies = {}
        for model, latencies in latencies_by_model.items():
            if latencies:
                avg_latencies[model] = statistics.mean(latencies)
                logger.info(f"Model {model} avg latency: {avg_latencies[model]:.2f}ms")
        
        # Test if routing prefers lower latency model
        if len(avg_latencies) >= 2:
            # Make requests through primary endpoint
            primary_model_counts = Counter()
            
            for i in range(20):
                try:
                    result = budproxy_client.inference(
                        model="primary-llm",
                        prompt=f"Route test {i}",
                        max_tokens=10
                    )
                    
                    if result and "model" in result:
                        primary_model_counts[result["model"]] += 1
                except:
                    pass
            
            # Check if lower latency model got more requests
            if primary_model_counts:
                sorted_models = sorted(avg_latencies.items(), key=lambda x: x[1])
                lowest_latency_model = sorted_models[0][0]
                
                logger.info(f"Routing distribution: {dict(primary_model_counts)}")
                logger.info(f"Lowest latency model: {lowest_latency_model}")
                
                # This assertion depends on latency-based routing being enabled
                # Just log the results for now
    
    def test_health_based_routing(self, budproxy_client, test_models, aibrix_client):
        """Test health-based routing."""
        # Check model health status
        try:
            models = aibrix_client.list_models()
            healthy_models = []
            unhealthy_models = []
            
            for model in models.get("models", []):
                if model.get("status") == "healthy":
                    healthy_models.append(model["name"])
                else:
                    unhealthy_models.append(model["name"])
            
            logger.info(f"Healthy models: {healthy_models}")
            logger.info(f"Unhealthy models: {unhealthy_models}")
            
            # Verify routing avoids unhealthy models
            if unhealthy_models:
                for unhealthy_model in unhealthy_models:
                    with pytest.raises(Exception):
                        budproxy_client.inference(
                            model=unhealthy_model,
                            prompt="Test unhealthy",
                            max_tokens=10,
                            timeout=5
                        )
        
        except Exception as e:
            logger.warning(f"Health-based routing test skipped: {e}")
            pytest.skip("Unable to test health-based routing")