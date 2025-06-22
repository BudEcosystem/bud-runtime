"""Kubernetes utilities for E2E tests."""

import time
import logging
import subprocess
from typing import Dict, List, Optional, Tuple
from contextlib import contextmanager

from kubernetes import client, config
from kubernetes.client.rest import ApiException
from kubernetes.stream import stream

logger = logging.getLogger(__name__)


def get_pod_status(
    k8s_client: client.CoreV1Api,
    namespace: str,
    label_selector: str = None,
    pod_name: str = None
) -> List[Dict[str, any]]:
    """Get status of pods."""
    try:
        if pod_name:
            pod = k8s_client.read_namespaced_pod(pod_name, namespace)
            pods = [pod]
        else:
            pods = k8s_client.list_namespaced_pod(
                namespace,
                label_selector=label_selector
            ).items
        
        pod_statuses = []
        for pod in pods:
            status = {
                "name": pod.metadata.name,
                "phase": pod.status.phase,
                "ready": all(c.ready for c in pod.status.container_statuses or []),
                "containers": []
            }
            
            if pod.status.container_statuses:
                for container in pod.status.container_statuses:
                    status["containers"].append({
                        "name": container.name,
                        "ready": container.ready,
                        "restart_count": container.restart_count,
                        "state": _get_container_state(container.state)
                    })
            
            pod_statuses.append(status)
        
        return pod_statuses
    
    except ApiException as e:
        logger.error(f"Failed to get pod status: {e}")
        return []


def _get_container_state(state) -> str:
    """Get container state as string."""
    if state.running:
        return "running"
    elif state.waiting:
        return f"waiting: {state.waiting.reason}"
    elif state.terminated:
        return f"terminated: {state.terminated.reason}"
    return "unknown"


def wait_for_deployment_ready(
    k8s_client: client.AppsV1Api,
    namespace: str,
    deployment_name: str,
    timeout: int = 300,
    interval: int = 5
) -> bool:
    """Wait for deployment to be ready."""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            deployment = k8s_client.read_namespaced_deployment(
                deployment_name, namespace
            )
            
            if deployment.status.ready_replicas == deployment.spec.replicas:
                logger.info(f"Deployment {deployment_name} is ready")
                return True
            
            logger.debug(
                f"Deployment {deployment_name}: "
                f"{deployment.status.ready_replicas}/{deployment.spec.replicas} ready"
            )
        
        except ApiException as e:
            logger.error(f"Error checking deployment: {e}")
        
        time.sleep(interval)
    
    logger.error(f"Deployment {deployment_name} not ready after {timeout}s")
    return False


def scale_deployment(
    k8s_client: client.AppsV1Api,
    namespace: str,
    deployment_name: str,
    replicas: int
) -> bool:
    """Scale a deployment."""
    try:
        # Get current deployment
        deployment = k8s_client.read_namespaced_deployment(
            deployment_name, namespace
        )
        
        # Update replicas
        deployment.spec.replicas = replicas
        
        # Apply update
        k8s_client.patch_namespaced_deployment(
            name=deployment_name,
            namespace=namespace,
            body=deployment
        )
        
        logger.info(f"Scaled {deployment_name} to {replicas} replicas")
        return True
    
    except ApiException as e:
        logger.error(f"Failed to scale deployment: {e}")
        return False


def get_pod_logs(
    k8s_client: client.CoreV1Api,
    namespace: str,
    pod_name: str,
    container: str = None,
    tail_lines: int = 100
) -> str:
    """Get pod logs."""
    try:
        logs = k8s_client.read_namespaced_pod_log(
            name=pod_name,
            namespace=namespace,
            container=container,
            tail_lines=tail_lines
        )
        return logs
    
    except ApiException as e:
        logger.error(f"Failed to get pod logs: {e}")
        return f"Error: {e}"


@contextmanager
def port_forward(
    cluster_context: str,
    namespace: str,
    service_name: str,
    local_port: int,
    remote_port: int
):
    """Context manager for port forwarding."""
    cmd = [
        "kubectl", "--context", cluster_context,
        "port-forward", "-n", namespace,
        f"svc/{service_name}", f"{local_port}:{remote_port}"
    ]
    
    logger.info(f"Starting port forward: {' '.join(cmd)}")
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Wait for port forward to be ready
    time.sleep(3)
    
    try:
        yield local_port
    finally:
        logger.info("Stopping port forward")
        process.terminate()
        process.wait(timeout=5)


def exec_in_pod(
    k8s_client: client.CoreV1Api,
    namespace: str,
    pod_name: str,
    command: List[str],
    container: str = None
) -> Tuple[str, str, int]:
    """Execute command in pod."""
    try:
        resp = stream(
            k8s_client.connect_get_namespaced_pod_exec,
            pod_name,
            namespace,
            command=command,
            container=container,
            stderr=True,
            stdin=False,
            stdout=True,
            tty=False,
            _preload_content=False
        )
        
        stdout = ""
        stderr = ""
        
        while resp.is_open():
            resp.update(timeout=1)
            if resp.peek_stdout():
                stdout += resp.read_stdout()
            if resp.peek_stderr():
                stderr += resp.read_stderr()
        
        exit_code = resp.returncode
        
        return stdout, stderr, exit_code
    
    except ApiException as e:
        logger.error(f"Failed to exec in pod: {e}")
        return "", str(e), 1


def wait_for_pod_ready(
    k8s_client: client.CoreV1Api,
    namespace: str,
    pod_name: str,
    timeout: int = 300
) -> bool:
    """Wait for a specific pod to be ready."""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            pod = k8s_client.read_namespaced_pod(pod_name, namespace)
            
            if pod.status.phase == "Running":
                if all(c.ready for c in pod.status.container_statuses or []):
                    logger.info(f"Pod {pod_name} is ready")
                    return True
            
            logger.debug(f"Pod {pod_name} status: {pod.status.phase}")
        
        except ApiException as e:
            logger.error(f"Error checking pod: {e}")
        
        time.sleep(5)
    
    logger.error(f"Pod {pod_name} not ready after {timeout}s")
    return False


def get_service_endpoints(
    k8s_client: client.CoreV1Api,
    namespace: str,
    service_name: str
) -> List[str]:
    """Get endpoints for a service."""
    try:
        endpoints = k8s_client.read_namespaced_endpoints(service_name, namespace)
        
        addresses = []
        for subset in endpoints.subsets or []:
            for address in subset.addresses or []:
                for port in subset.ports or []:
                    addresses.append(f"{address.ip}:{port.port}")
        
        return addresses
    
    except ApiException as e:
        logger.error(f"Failed to get service endpoints: {e}")
        return []