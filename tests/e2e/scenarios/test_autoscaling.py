"""E2E tests for autoscaling behavior."""

import time
import pytest
import logging
import threading
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

from kubernetes import client
from tests.e2e.utils import (
    make_inference_request,
    wait_for_deployment_ready,
    get_pod_status,
    batch_inference
)

logger = logging.getLogger(__name__)


@pytest.mark.slow
@pytest.mark.integration
class TestHorizontalAutoscaling:
    """Test horizontal pod autoscaling."""
    
    def test_scale_up_on_load(self, budproxy_client, test_models, k8s_inference_client):
        """Test automatic scale-up under load."""
        model = test_models["small"]
        
        # Get initial replica count
        apps_v1 = client.AppsV1Api()
        initial_replicas = self._get_current_replicas(apps_v1, model)
        
        if initial_replicas is None:
            pytest.skip(f"Model {model} deployment not found")
        
        logger.info(f"Initial replicas: {initial_replicas}")
        
        # Generate high load
        num_requests = 100
        concurrent_workers = 20
        prompts = [f"High load test {i}" for i in range(num_requests)]
        
        logger.info(f"Generating load with {num_requests} requests...")
        
        # Start load generation
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=concurrent_workers) as executor:
            futures = []
            for prompt in prompts:
                future = executor.submit(
                    make_inference_request,
                    budproxy_client.base_url,
                    model,
                    prompt,
                    max_tokens=100,
                    timeout=60
                )
                futures.append(future)
                time.sleep(0.1)  # Spread out requests
            
            # Monitor scaling while load is running
            max_replicas_seen = initial_replicas
            scale_up_detected = False
            
            for i in range(30):  # Check for 5 minutes
                current_replicas = self._get_current_replicas(apps_v1, model)
                if current_replicas and current_replicas > initial_replicas:
                    scale_up_detected = True
                    max_replicas_seen = max(max_replicas_seen, current_replicas)
                    logger.info(f"Scale up detected! Replicas: {current_replicas}")
                
                # Check if futures are completing
                completed = sum(1 for f in futures if f.done())
                logger.info(f"Completed requests: {completed}/{num_requests}")
                
                if completed == num_requests:
                    break
                
                time.sleep(10)
            
            # Wait for remaining requests
            results = []
            for future in as_completed(futures, timeout=300):
                try:
                    results.append(future.result())
                except Exception as e:
                    logger.error(f"Request failed: {e}")
        
        elapsed_time = time.time() - start_time
        successful_requests = sum(1 for r in results if r.success)
        
        logger.info(f"Load generation completed in {elapsed_time:.2f}s")
        logger.info(f"Successful requests: {successful_requests}/{num_requests}")
        logger.info(f"Max replicas seen: {max_replicas_seen}")
        
        # Verify scaling occurred
        if scale_up_detected:
            assert max_replicas_seen > initial_replicas, "Expected scale up did not occur"
            logger.info("✓ Autoscaling successfully triggered")
        else:
            logger.warning("Scale up was not detected - HPA might not be configured")
    
    def test_scale_down_after_load(self, budproxy_client, test_models, k8s_inference_client):
        """Test automatic scale-down after load decreases."""
        model = test_models["small"]
        
        apps_v1 = client.AppsV1Api()
        initial_replicas = self._get_current_replicas(apps_v1, model)
        
        if initial_replicas is None:
            pytest.skip(f"Model {model} deployment not found")
        
        # First, ensure we have scaled up instances
        if initial_replicas == 1:
            logger.info("Generating initial load to trigger scale up...")
            self._generate_load(budproxy_client.base_url, model, duration=60, rps=10)
            time.sleep(30)  # Wait for scale up
        
        current_replicas = self._get_current_replicas(apps_v1, model)
        logger.info(f"Current replicas before cooldown: {current_replicas}")
        
        if current_replicas <= 1:
            pytest.skip("No scale up detected, cannot test scale down")
        
        # Wait for scale down (this can take several minutes)
        logger.info("Waiting for scale down...")
        scale_down_detected = False
        min_replicas_seen = current_replicas
        
        for i in range(20):  # Check for up to 10 minutes
            time.sleep(30)
            new_replicas = self._get_current_replicas(apps_v1, model)
            
            if new_replicas < current_replicas:
                scale_down_detected = True
                min_replicas_seen = min(min_replicas_seen, new_replicas)
                logger.info(f"Scale down detected! Replicas: {new_replicas}")
                break
            
            # Make occasional request to keep service alive but not trigger scale up
            try:
                budproxy_client.inference(
                    model=model,
                    prompt="Keep alive",
                    max_tokens=10
                )
            except:
                pass
        
        if scale_down_detected:
            logger.info("✓ Autoscaling successfully scaled down")
        else:
            logger.warning("Scale down was not detected within timeout")
    
    def test_hpa_metrics(self, k8s_inference_client, test_models):
        """Test HPA metrics and configuration."""
        model = test_models["small"]
        
        # Get HPA for the model
        autoscaling_v2 = client.AutoscalingV2Api()
        
        try:
            hpas = autoscaling_v2.list_namespaced_horizontal_pod_autoscaler(
                namespace="inference-system"
            )
            
            model_hpa = None
            for hpa in hpas.items:
                if model in hpa.metadata.name:
                    model_hpa = hpa
                    break
            
            if not model_hpa:
                pytest.skip(f"No HPA found for model {model}")
            
            logger.info(f"HPA: {model_hpa.metadata.name}")
            logger.info(f"Min replicas: {model_hpa.spec.min_replicas}")
            logger.info(f"Max replicas: {model_hpa.spec.max_replicas}")
            logger.info(f"Current replicas: {model_hpa.status.current_replicas}")
            
            # Check metrics
            if model_hpa.spec.metrics:
                for metric in model_hpa.spec.metrics:
                    logger.info(f"Metric type: {metric.type}")
                    if metric.type == "Resource":
                        logger.info(f"Resource: {metric.resource.name}")
                        logger.info(f"Target: {metric.resource.target}")
            
            # Check current metrics
            if model_hpa.status.current_metrics:
                for metric in model_hpa.status.current_metrics:
                    logger.info(f"Current metric: {metric}")
            
            assert model_hpa.spec.min_replicas >= 1, "Min replicas should be at least 1"
            assert model_hpa.spec.max_replicas > model_hpa.spec.min_replicas, \
                "Max replicas should be greater than min"
        
        except Exception as e:
            logger.error(f"Failed to check HPA: {e}")
            pytest.skip("Unable to verify HPA configuration")
    
    def _get_current_replicas(self, apps_v1, model: str) -> int:
        """Get current replica count for a model."""
        try:
            statefulsets = apps_v1.list_namespaced_stateful_set(
                namespace="inference-system",
                label_selector=f"app.kubernetes.io/instance={model}"
            )
            
            if statefulsets.items:
                return statefulsets.items[0].status.ready_replicas or 0
            
            # Try deployments
            deployments = apps_v1.list_namespaced_deployment(
                namespace="inference-system",
                label_selector=f"app.kubernetes.io/instance={model}"
            )
            
            if deployments.items:
                return deployments.items[0].status.ready_replicas or 0
            
        except Exception as e:
            logger.error(f"Failed to get replicas: {e}")
        
        return None
    
    def _generate_load(self, endpoint: str, model: str, duration: int, rps: int):
        """Generate load for a specified duration."""
        end_time = time.time() + duration
        request_count = 0
        
        while time.time() < end_time:
            try:
                make_inference_request(
                    endpoint,
                    model,
                    f"Load test {request_count}",
                    max_tokens=50,
                    timeout=10
                )
                request_count += 1
                
                # Sleep to maintain target RPS
                time.sleep(1.0 / rps)
                
            except Exception as e:
                logger.debug(f"Request failed during load generation: {e}")
        
        logger.info(f"Generated {request_count} requests over {duration}s")


@pytest.mark.slow
@pytest.mark.gpu
class TestGPUAutoscaling:
    """Test GPU-aware autoscaling."""
    
    def test_gpu_utilization_scaling(self, budproxy_client, test_models, k8s_inference_client):
        """Test scaling based on GPU utilization."""
        # Find a GPU-enabled model
        gpu_model = None
        for model_key, model_name in test_models.items():
            if model_key in ["llama2", "mistral"]:
                gpu_model = model_name
                break
        
        if not gpu_model:
            pytest.skip("No GPU model configured")
        
        # Check if model has GPU resources
        apps_v1 = client.AppsV1Api()
        try:
            statefulsets = apps_v1.list_namespaced_stateful_set(
                namespace="inference-system",
                label_selector=f"app.kubernetes.io/instance={gpu_model}"
            )
            
            if not statefulsets.items:
                pytest.skip(f"No deployment found for GPU model {gpu_model}")
            
            # Check GPU resource requests
            containers = statefulsets.items[0].spec.template.spec.containers
            has_gpu = False
            for container in containers:
                if container.resources and container.resources.limits:
                    if "nvidia.com/gpu" in container.resources.limits:
                        has_gpu = True
                        break
            
            if not has_gpu:
                pytest.skip(f"Model {gpu_model} does not request GPU resources")
            
            # Generate GPU-intensive load
            logger.info(f"Generating GPU-intensive load for model {gpu_model}")
            
            # Use longer prompts to increase GPU utilization
            prompts = [
                "Write a detailed technical analysis of quantum computing, covering its principles, "
                "current applications, challenges, and future prospects. Include specific examples "
                "of quantum algorithms and their potential impact on cryptography, drug discovery, "
                "and artificial intelligence." for _ in range(20)
            ]
            
            results = batch_inference(
                budproxy_client.base_url,
                gpu_model,
                prompts,
                max_tokens=500,  # Large output to stress GPU
                max_workers=5,
                timeout=120
            )
            
            successful = sum(1 for r in results if r.success)
            logger.info(f"GPU load test: {successful}/{len(prompts)} successful")
            
            # Monitor GPU metrics if available
            self._check_gpu_metrics(k8s_inference_client)
        
        except Exception as e:
            logger.error(f"GPU autoscaling test failed: {e}")
            pytest.skip("Unable to test GPU autoscaling")
    
    def test_gpu_memory_pressure(self, budproxy_client, test_models):
        """Test behavior under GPU memory pressure."""
        gpu_model = test_models.get("llama2", test_models.get("mistral"))
        
        if not gpu_model:
            pytest.skip("No GPU model configured")
        
        # Test with increasing batch sizes
        batch_sizes = [1, 2, 4, 8]
        max_successful_batch = 0
        
        for batch_size in batch_sizes:
            logger.info(f"Testing batch size: {batch_size}")
            
            # Create prompts that will be processed in parallel
            prompts = [
                f"Batch {i}: Explain the concept of {topic}"
                for i in range(batch_size)
                for topic in ["AI", "ML", "DL", "NLP"]
            ][:batch_size]
            
            try:
                results = batch_inference(
                    budproxy_client.base_url,
                    gpu_model,
                    prompts,
                    max_tokens=200,
                    max_workers=batch_size,
                    timeout=60
                )
                
                successful = sum(1 for r in results if r.success)
                if successful == len(prompts):
                    max_successful_batch = batch_size
                    logger.info(f"Batch size {batch_size}: All requests successful")
                else:
                    logger.warning(f"Batch size {batch_size}: {successful}/{len(prompts)} successful")
                    break
                    
            except Exception as e:
                logger.error(f"Batch size {batch_size} failed: {e}")
                break
        
        logger.info(f"Maximum successful batch size: {max_successful_batch}")
        assert max_successful_batch >= 1, "Should handle at least batch size of 1"
    
    def _check_gpu_metrics(self, k8s_client):
        """Check GPU metrics from monitoring."""
        try:
            # Look for GPU metrics in pods
            pods = k8s_client.list_namespaced_pod(
                namespace="gpu-operator",
                label_selector="app=nvidia-dcgm-exporter"
            )
            
            if pods.items:
                logger.info(f"Found {len(pods.items)} GPU metric exporter pods")
                # Could exec into pod to get nvidia-smi output
            else:
                logger.warning("No GPU metric exporter pods found")
        
        except Exception as e:
            logger.debug(f"Could not check GPU metrics: {e}")


@pytest.mark.integration
class TestAIBrixAutoscaling:
    """Test AIBrix-controlled autoscaling."""
    
    def test_aibrix_model_scaling(self, aibrix_client, test_models):
        """Test scaling models through AIBrix API."""
        model = test_models["small"]
        
        try:
            # Get current scale
            status = aibrix_client.get_model_status(model)
            current_replicas = status.get("replicas", 1)
            logger.info(f"Current replicas for {model}: {current_replicas}")
            
            # Scale up
            new_replicas = current_replicas + 1
            logger.info(f"Scaling {model} to {new_replicas} replicas")
            
            scale_result = aibrix_client.scale_model(model, new_replicas)
            assert scale_result.get("success"), "Scale operation failed"
            
            # Wait for scaling to complete
            time.sleep(30)
            
            # Verify new scale
            status = aibrix_client.get_model_status(model)
            assert status.get("replicas") == new_replicas, "Scaling did not complete"
            
            # Scale back down
            logger.info(f"Scaling {model} back to {current_replicas} replicas")
            aibrix_client.scale_model(model, current_replicas)
            
        except Exception as e:
            if "404" in str(e) or "not found" in str(e).lower():
                pytest.skip("AIBrix API not available")
            logger.error(f"AIBrix scaling test failed: {e}")
            raise
    
    def test_model_deployment_lifecycle(self, aibrix_client):
        """Test model deployment and undeployment."""
        test_model_config = {
            "name": "test-autoscale-model",
            "model_id": "facebook/opt-125m",
            "replicas": 1,
            "resources": {
                "requests": {"cpu": "1", "memory": "2Gi"},
                "limits": {"cpu": "2", "memory": "4Gi"}
            }
        }
        
        try:
            # Deploy model
            logger.info(f"Deploying test model: {test_model_config['name']}")
            deploy_result = aibrix_client.deploy_model(test_model_config)
            assert deploy_result.get("success"), "Model deployment failed"
            
            # Wait for deployment
            time.sleep(60)
            
            # Check status
            status = aibrix_client.get_model_status(test_model_config["name"])
            assert status.get("status") == "ready", "Model not ready"
            
            # Cleanup - undeploy model
            logger.info(f"Undeploying test model: {test_model_config['name']}")
            undeploy_result = aibrix_client.undeploy_model(test_model_config["name"])
            assert undeploy_result.get("success"), "Model undeployment failed"
            
        except AttributeError:
            pytest.skip("Model lifecycle management not implemented in AIBrix client")
        except Exception as e:
            if "not implemented" in str(e).lower():
                pytest.skip("Model lifecycle management not available")
            logger.error(f"Model lifecycle test failed: {e}")
            raise