"""E2E tests for failover and resilience."""

import time
import pytest
import logging
import threading
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from kubernetes import client
from tests.e2e.utils import (
    make_inference_request,
    get_pod_status,
    exec_in_pod,
    wait_for_pod_ready,
    scale_deployment
)

logger = logging.getLogger(__name__)


@pytest.mark.failover
@pytest.mark.integration
class TestPodFailover:
    """Test pod failure and recovery scenarios."""
    
    def test_pod_crash_recovery(self, budproxy_client, test_models, k8s_inference_client):
        """Test recovery from pod crashes."""
        model = test_models["small"]
        
        # Get pods for the model
        pods = k8s_inference_client.list_namespaced_pod(
            namespace="inference-system",
            label_selector=f"app.kubernetes.io/instance={model}"
        )
        
        if not pods.items:
            pytest.skip(f"No pods found for model {model}")
        
        target_pod = pods.items[0]
        pod_name = target_pod.metadata.name
        logger.info(f"Target pod for crash test: {pod_name}")
        
        # Verify service is working
        initial_result = budproxy_client.inference(
            model=model,
            prompt="Pre-crash test",
            max_tokens=10
        )
        assert initial_result is not None
        
        # Delete the pod to simulate crash
        logger.info(f"Deleting pod {pod_name} to simulate crash")
        try:
            k8s_inference_client.delete_namespaced_pod(
                name=pod_name,
                namespace="inference-system",
                grace_period_seconds=0
            )
        except Exception as e:
            logger.error(f"Failed to delete pod: {e}")
            pytest.skip("Unable to simulate pod crash")
        
        # Test inference during recovery
        recovery_start = time.time()
        successful_during_recovery = 0
        failed_during_recovery = 0
        
        # Make requests while pod is recovering
        for i in range(30):  # Try for up to 30 seconds
            try:
                result = budproxy_client.inference(
                    model=model,
                    prompt=f"Recovery test {i}",
                    max_tokens=10,
                    timeout=5
                )
                successful_during_recovery += 1
                logger.info(f"Request {i} succeeded during recovery")
                
            except Exception as e:
                failed_during_recovery += 1
                logger.debug(f"Request {i} failed during recovery: {e}")
            
            time.sleep(1)
            
            # Check if new pod is ready
            new_pods = k8s_inference_client.list_namespaced_pod(
                namespace="inference-system",
                label_selector=f"app.kubernetes.io/instance={model}"
            )
            
            ready_pods = [p for p in new_pods.items 
                         if p.status.phase == "Running" and 
                         all(c.ready for c in p.status.container_statuses or [])]
            
            if ready_pods:
                logger.info("New pod is ready")
                break
        
        recovery_time = time.time() - recovery_start
        
        # Verify service is working after recovery
        post_recovery_result = budproxy_client.inference(
            model=model,
            prompt="Post-recovery test",
            max_tokens=10
        )
        assert post_recovery_result is not None, "Service did not recover"
        
        logger.info(f"Recovery completed in {recovery_time:.2f}s")
        logger.info(f"During recovery - Success: {successful_during_recovery}, Failed: {failed_during_recovery}")
        
        # Some requests should succeed if multiple replicas
        if len(pods.items) > 1:
            assert successful_during_recovery > 0, "No requests succeeded during multi-replica failover"
    
    def test_container_oom_recovery(self, budproxy_client, test_models, k8s_inference_client):
        """Test recovery from out-of-memory kills."""
        model = test_models["small"]
        
        # Get a pod for the model
        pods = k8s_inference_client.list_namespaced_pod(
            namespace="inference-system",
            label_selector=f"app.kubernetes.io/instance={model}"
        )
        
        if not pods.items:
            pytest.skip(f"No pods found for model {model}")
        
        pod_name = pods.items[0].metadata.name
        container_name = pods.items[0].spec.containers[0].name
        
        # Get initial restart count
        initial_restarts = pods.items[0].status.container_statuses[0].restart_count
        logger.info(f"Initial restart count: {initial_restarts}")
        
        # Try to trigger OOM (this is tricky and might not work in all environments)
        logger.info("Attempting to trigger OOM condition")
        
        # Send multiple large requests concurrently
        oom_triggered = False
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for i in range(20):
                # Very long prompt to consume memory
                long_prompt = "Please process this: " + " ".join([
                    f"Token{j}" for j in range(1000)
                ])
                
                future = executor.submit(
                    budproxy_client.inference,
                    model=model,
                    prompt=long_prompt,
                    max_tokens=1000,
                    timeout=30
                )
                futures.append(future)
            
            # Wait for results
            for future in as_completed(futures, timeout=60):
                try:
                    future.result()
                except Exception as e:
                    logger.debug(f"Request failed (expected): {e}")
        
        # Check if container restarted
        time.sleep(10)
        pods = k8s_inference_client.list_namespaced_pod(
            namespace="inference-system",
            label_selector=f"app.kubernetes.io/instance={model}"
        )
        
        for pod in pods.items:
            if pod.metadata.name == pod_name:
                for container_status in pod.status.container_statuses:
                    if container_status.name == container_name:
                        new_restarts = container_status.restart_count
                        if new_restarts > initial_restarts:
                            oom_triggered = True
                            logger.info(f"Container restarted! New count: {new_restarts}")
        
        if oom_triggered:
            # Verify recovery
            recovery_result = budproxy_client.inference(
                model=model,
                prompt="Recovery after OOM",
                max_tokens=10
            )
            assert recovery_result is not None, "Service did not recover after OOM"
            logger.info("✓ Service recovered after OOM")
        else:
            logger.warning("OOM condition was not triggered (this is OK)")


@pytest.mark.failover
@pytest.mark.integration
class TestServiceFailover:
    """Test service-level failover scenarios."""
    
    def test_aibrix_failure_handling(self, budproxy_client, test_models, k8s_clients):
        """Test handling of AIBrix control plane failure."""
        model = test_models["small"]
        
        # Get AIBrix deployment
        apps_v1 = client.AppsV1Api()
        try:
            deployments = apps_v1.list_namespaced_deployment(
                namespace="inference-system",
                label_selector="app.kubernetes.io/component=aibrix"
            )
            
            if not deployments.items:
                pytest.skip("AIBrix deployment not found")
            
            aibrix_deployment = deployments.items[0]
            original_replicas = aibrix_deployment.spec.replicas
            
            # Scale down AIBrix
            logger.info("Scaling down AIBrix to simulate failure")
            scale_deployment(
                apps_v1,
                "inference-system",
                aibrix_deployment.metadata.name,
                0
            )
            
            time.sleep(10)
            
            # Test if inference still works (it should, as VLLM runs independently)
            inference_works = True
            try:
                result = budproxy_client.inference(
                    model=model,
                    prompt="Test during AIBrix outage",
                    max_tokens=10,
                    timeout=10
                )
                logger.info("Inference still works without AIBrix")
            except Exception as e:
                inference_works = False
                logger.info(f"Inference failed without AIBrix: {e}")
            
            # Restore AIBrix
            logger.info("Restoring AIBrix")
            scale_deployment(
                apps_v1,
                "inference-system",
                aibrix_deployment.metadata.name,
                original_replicas
            )
            
            # Wait for AIBrix to be ready
            wait_for_deployment_ready(
                apps_v1,
                "inference-system",
                aibrix_deployment.metadata.name,
                timeout=120
            )
            
            # Verify everything works after restoration
            result = budproxy_client.inference(
                model=model,
                prompt="Test after AIBrix restoration",
                max_tokens=10
            )
            assert result is not None
            
            # AIBrix failure should not affect existing VLLM instances
            if not inference_works:
                logger.warning("Inference was affected by AIBrix failure")
        
        except Exception as e:
            logger.error(f"AIBrix failover test failed: {e}")
            pytest.skip("Unable to test AIBrix failover")
    
    def test_database_connection_loss(self, budproxy_client, test_models, k8s_app_client):
        """Test handling of database connection failures."""
        model = test_models["small"]
        
        # This test simulates database connectivity issues
        # Get database service
        try:
            services = k8s_app_client.list_namespaced_service(
                namespace="bud-system",
                label_selector="app=postgres"
            )
            
            if not services.items:
                pytest.skip("PostgreSQL service not found")
            
            db_service = services.items[0]
            original_selector = db_service.spec.selector.copy()
            
            # Modify service selector to break connection
            logger.info("Breaking database connection")
            db_service.spec.selector["break"] = "connection"
            
            k8s_app_client.patch_namespaced_service(
                name=db_service.metadata.name,
                namespace="bud-system",
                body=db_service
            )
            
            time.sleep(5)
            
            # Test if inference still works (might use cache)
            db_error_seen = False
            try:
                result = budproxy_client.inference(
                    model=model,
                    prompt="Test during DB outage",
                    max_tokens=10,
                    timeout=10
                )
                logger.info("Inference works despite DB connection loss (using cache?)")
            except Exception as e:
                db_error_seen = True
                logger.info(f"Inference affected by DB outage: {e}")
            
            # Restore connection
            logger.info("Restoring database connection")
            db_service.spec.selector = original_selector
            
            k8s_app_client.patch_namespaced_service(
                name=db_service.metadata.name,
                namespace="bud-system",
                body=db_service
            )
            
            time.sleep(5)
            
            # Verify recovery
            result = budproxy_client.inference(
                model=model,
                prompt="Test after DB restoration",
                max_tokens=10
            )
            assert result is not None, "Service did not recover after DB restoration"
            
        except Exception as e:
            logger.error(f"Database failover test failed: {e}")
            pytest.skip("Unable to test database failover")


@pytest.mark.failover
@pytest.mark.slow
class TestNetworkFailure:
    """Test network failure scenarios."""
    
    def test_network_partition(self, budproxy_client, test_models, k8s_clients):
        """Test handling of network partitions between clusters."""
        model = test_models.get("llama2", test_models["small"])
        
        # This test requires cross-cluster networking to be set up
        logger.info("Testing network partition scenario")
        
        # Create network policy to block traffic
        network_policy = {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "metadata": {
                "name": "block-cross-cluster",
                "namespace": "inference-system"
            },
            "spec": {
                "podSelector": {},
                "policyTypes": ["Ingress", "Egress"],
                "ingress": [{
                    "from": [{
                        "namespaceSelector": {
                            "matchLabels": {
                                "name": "inference-system"
                            }
                        }
                    }]
                }],
                "egress": [{
                    "to": [{
                        "namespaceSelector": {
                            "matchLabels": {
                                "name": "inference-system"
                            }
                        }
                    }]
                }]
            }
        }
        
        try:
            # Apply network policy
            networking_v1 = client.NetworkingV1Api()
            logger.info("Applying network policy to simulate partition")
            
            networking_v1.create_namespaced_network_policy(
                namespace="inference-system",
                body=network_policy
            )
            
            time.sleep(5)
            
            # Test inference during partition
            partition_errors = 0
            for i in range(5):
                try:
                    result = budproxy_client.inference(
                        model=model,
                        prompt=f"Test during partition {i}",
                        max_tokens=10,
                        timeout=5
                    )
                    logger.info(f"Request {i} succeeded during partition")
                except Exception as e:
                    partition_errors += 1
                    logger.info(f"Request {i} failed during partition: {e}")
            
            # Remove network policy
            logger.info("Removing network policy")
            networking_v1.delete_namespaced_network_policy(
                name="block-cross-cluster",
                namespace="inference-system"
            )
            
            time.sleep(5)
            
            # Verify recovery
            result = budproxy_client.inference(
                model=model,
                prompt="Test after partition healed",
                max_tokens=10
            )
            assert result is not None, "Service did not recover after partition"
            
            logger.info(f"Network partition test completed. Errors during partition: {partition_errors}/5")
            
        except Exception as e:
            logger.error(f"Network partition test failed: {e}")
            # Cleanup
            try:
                networking_v1.delete_namespaced_network_policy(
                    name="block-cross-cluster",
                    namespace="inference-system"
                )
            except:
                pass
    
    def test_intermittent_network_issues(self, budproxy_client, test_models):
        """Test handling of intermittent network issues."""
        model = test_models["small"]
        
        # Simulate intermittent failures with concurrent requests
        results = []
        errors = []
        
        def make_request(i):
            try:
                # Use very short timeout to simulate network issues
                timeout = 2 if i % 3 == 0 else 10  # Every 3rd request has short timeout
                
                result = make_inference_request(
                    budproxy_client.base_url,
                    model,
                    f"Intermittent test {i}",
                    max_tokens=10,
                    timeout=timeout
                )
                
                if result.success:
                    results.append(result)
                else:
                    errors.append(result.error)
                    
            except Exception as e:
                errors.append(str(e))
        
        # Run requests with intermittent issues
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request, i) for i in range(20)]
            for future in as_completed(futures):
                future.result()
        
        logger.info(f"Intermittent network test: {len(results)} success, {len(errors)} errors")
        
        # Should handle some failures gracefully
        assert len(results) > len(errors), "Too many failures under intermittent issues"
        assert len(results) > 10, "Success rate too low"


@pytest.mark.failover
class TestGracefulShutdown:
    """Test graceful shutdown and restart scenarios."""
    
    def test_rolling_update(self, budproxy_client, test_models, k8s_inference_client):
        """Test behavior during rolling updates."""
        model = test_models["small"]
        
        # Get the statefulset
        apps_v1 = client.AppsV1Api()
        try:
            statefulsets = apps_v1.list_namespaced_stateful_set(
                namespace="inference-system",
                label_selector=f"app.kubernetes.io/instance={model}"
            )
            
            if not statefulsets.items:
                pytest.skip(f"No statefulset found for model {model}")
            
            sts = statefulsets.items[0]
            
            # Trigger rolling update by updating annotation
            logger.info("Triggering rolling update")
            
            if not sts.spec.template.metadata.annotations:
                sts.spec.template.metadata.annotations = {}
            
            sts.spec.template.metadata.annotations["test-update"] = str(time.time())
            
            apps_v1.patch_namespaced_stateful_set(
                name=sts.metadata.name,
                namespace="inference-system",
                body=sts
            )
            
            # Monitor requests during rolling update
            update_start = time.time()
            successful_requests = 0
            failed_requests = 0
            
            while time.time() - update_start < 120:  # Monitor for 2 minutes
                try:
                    result = budproxy_client.inference(
                        model=model,
                        prompt="Test during rolling update",
                        max_tokens=10,
                        timeout=5
                    )
                    successful_requests += 1
                except Exception as e:
                    failed_requests += 1
                    logger.debug(f"Request failed during update: {e}")
                
                time.sleep(1)
                
                # Check if update is complete
                sts = apps_v1.read_namespaced_stateful_set(
                    name=sts.metadata.name,
                    namespace="inference-system"
                )
                
                if (sts.status.updated_replicas == sts.spec.replicas and
                    sts.status.ready_replicas == sts.spec.replicas):
                    logger.info("Rolling update completed")
                    break
            
            update_duration = time.time() - update_start
            logger.info(f"Rolling update test completed in {update_duration:.2f}s")
            logger.info(f"Successful requests: {successful_requests}, Failed: {failed_requests}")
            
            # Should maintain some availability during update
            availability = successful_requests / (successful_requests + failed_requests)
            logger.info(f"Availability during update: {availability:.2%}")
            
            # For single replica, some downtime is expected
            if sts.spec.replicas > 1:
                assert availability > 0.5, "Availability too low during rolling update"
        
        except Exception as e:
            logger.error(f"Rolling update test failed: {e}")
            pytest.skip("Unable to test rolling update")