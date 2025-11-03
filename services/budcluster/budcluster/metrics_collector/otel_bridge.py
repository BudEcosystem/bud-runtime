"""Bridge between Prometheus metrics collection and OpenTelemetry Collector.

This module manages the integration between cluster Prometheus instances and
the central OTel Collector, handling port-forwarding and metric transformation.
"""

import asyncio
import socket
import subprocess
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
import yaml
from budmicroframe.commons.logging import get_logger

from ..commons.config import app_settings


logger = get_logger(__name__)

# Maximum concurrent port-forwards to prevent resource exhaustion
MAX_CONCURRENT_FORWARDS = 50


@contextmanager
def secure_kubeconfig_file(kubeconfig: str | dict, cluster_id: str):
    """Context manager for secure kubeconfig file handling.

    Ensures temporary kubeconfig files are always cleaned up, even on errors.
    Uses explicit error logging instead of silent failures.

    Args:
        kubeconfig: Kubernetes configuration as string or dict
        cluster_id: Cluster identifier for logging

    Yields:
        Path to temporary kubeconfig file
    """
    temp_file = None
    try:
        # Create temporary file with delete=False for explicit control
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            if isinstance(kubeconfig, dict):
                yaml.dump(kubeconfig, f)
            else:
                f.write(kubeconfig)
            temp_file = Path(f.name)

        logger.debug(f"Created temporary kubeconfig for cluster {cluster_id}: {temp_file}")
        yield str(temp_file)
    finally:
        # Always cleanup, with explicit error logging
        if temp_file:
            try:
                temp_file.unlink(missing_ok=True)
                logger.debug(f"Cleaned up kubeconfig for cluster {cluster_id}: {temp_file}")
            except Exception as e:
                logger.error(
                    f"Failed to clean up kubeconfig {temp_file} for cluster {cluster_id}: {e}. "
                    "This may leak sensitive credentials!"
                )


class OTelBridge:
    """Manages the bridge between Prometheus metrics and OTel Collector.

    This class handles:
    1. Port-forwarding to cluster Prometheus instances
    2. Scraping metrics from Prometheus
    3. Transforming and sending metrics to OTel Collector
    4. Managing dynamic scrape configurations
    """

    def __init__(
        self,
        otel_endpoint: str = None,
        otel_headers: Optional[Dict[str, str]] = None,
    ):
        """Initialize the OTel bridge.

        Args:
            otel_endpoint: OTel Collector HTTP endpoint (default from env)
            otel_headers: Optional headers for OTel requests
        """
        self.otel_endpoint = otel_endpoint or app_settings.otel_collector_endpoint or "http://localhost:4318"
        self.otel_headers = otel_headers or {}

        # Track active port-forwards
        self.active_forwards: Dict[str, Dict[str, Any]] = {}

        # Track scrape configurations
        self.scrape_configs: Dict[str, Dict[str, Any]] = {}

    async def setup_cluster_scraping(
        self,
        cluster_id: str,
        cluster_name: str,
        cluster_platform: str,
        kubeconfig: str,
        prometheus_namespace: str = "bud-system",
        prometheus_service: str = "prometheus",
    ) -> Tuple[bool, Optional[str]]:
        """Set up scraping for a cluster by configuring port-forward.

        Args:
            cluster_id: Unique cluster identifier
            cluster_name: Human-readable cluster name
            cluster_platform: Cluster platform (eks, aks, openshift)
            kubeconfig: Kubernetes configuration as string
            prometheus_namespace: Namespace where Prometheus is deployed
            prometheus_service: Prometheus service name

        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Check if already configured
            if cluster_id in self.active_forwards:
                logger.info(f"Cluster {cluster_id} already configured for scraping")
                return True, None

            # Start port-forward
            local_port = await self._start_port_forward(
                cluster_id, kubeconfig, prometheus_namespace, prometheus_service
            )

            if not local_port:
                return False, "Failed to establish port-forward"

            # Store configuration
            self.scrape_configs[cluster_id] = {
                "cluster_name": cluster_name,
                "cluster_platform": cluster_platform,
                "prometheus_endpoint": f"http://localhost:{local_port}",
                "namespace": prometheus_namespace,
                "service": prometheus_service,
            }

            # Update OTel configuration dynamically
            await self._update_otel_config(cluster_id, cluster_name, local_port)

            logger.info(f"Successfully configured scraping for cluster {cluster_id} on port {local_port}")
            return True, None

        except Exception as e:
            error_msg = f"Failed to setup scraping for cluster {cluster_id}: {e}"
            logger.error(error_msg)
            return False, error_msg

    async def _start_port_forward(
        self,
        cluster_id: str,
        kubeconfig: str,
        namespace: str,
        service: str,
    ) -> Optional[int]:
        """Start kubectl port-forward to Prometheus service.

        Returns:
            Local port number if successful, None otherwise
        """
        kubeconfig_path = None
        process = None
        try:
            # Check port-forward capacity to prevent resource exhaustion
            if len(self.active_forwards) >= MAX_CONCURRENT_FORWARDS:
                logger.error(
                    f"Maximum concurrent port-forwards ({MAX_CONCURRENT_FORWARDS}) reached. "
                    f"Cannot add cluster {cluster_id}."
                )
                return None

            # Check if kubectl is available
            kubectl_check = subprocess.run(["which", "kubectl"], capture_output=True, text=True, timeout=5)
            if kubectl_check.returncode != 0:
                logger.error("kubectl not found in PATH")
                return None

            # Write kubeconfig to temporary file
            with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
                if isinstance(kubeconfig, dict):
                    yaml.dump(kubeconfig, f)
                else:
                    f.write(kubeconfig)
                kubeconfig_path = f.name

            # Validate kubeconfig
            logger.debug(f"Testing kubeconfig for cluster {cluster_id}")
            test_cmd = [
                "kubectl",
                "--kubeconfig",
                kubeconfig_path,
            ]

            # Add insecure flag if SSL verification is disabled
            if not app_settings.validate_certs:
                test_cmd.append("--insecure-skip-tls-verify")
                logger.debug("SSL verification disabled for kubectl commands")

            test_cmd.extend(["get", "nodes", "--request-timeout=10s"])
            test_result = subprocess.run(test_cmd, capture_output=True, text=True, timeout=15)
            if test_result.returncode != 0:
                logger.error(f"Invalid kubeconfig or cluster unreachable: {test_result.stderr}")
                return None

            # Check if the Prometheus service exists
            logger.debug(f"Checking for Prometheus service {service} in namespace {namespace}")
            svc_cmd = [
                "kubectl",
                "--kubeconfig",
                kubeconfig_path,
            ]

            # Add insecure flag if SSL verification is disabled
            if not app_settings.validate_certs:
                svc_cmd.append("--insecure-skip-tls-verify")

            svc_cmd.extend(["-n", namespace, "get", "service", service, "--request-timeout=10s"])
            svc_result = subprocess.run(svc_cmd, capture_output=True, text=True, timeout=15)
            if svc_result.returncode != 0:
                logger.error(f"Prometheus service {service} not found in namespace {namespace}: {svc_result.stderr}")
                # Try to list available services for debugging
                list_cmd = ["kubectl", "--kubeconfig", kubeconfig_path]
                if not app_settings.validate_certs:
                    list_cmd.append("--insecure-skip-tls-verify")
                list_cmd.extend(["-n", namespace, "get", "services"])
                list_result = subprocess.run(list_cmd, capture_output=True, text=True, timeout=10)
                if list_result.returncode == 0:
                    logger.info(f"Available services in {namespace}:\n{list_result.stdout}")
                return None

            # Find an available port
            local_port = self._find_available_port()

            # Build port-forward command
            cmd = [
                "kubectl",
                "--kubeconfig",
                kubeconfig_path,
            ]

            # Add insecure flag if SSL verification is disabled
            if not app_settings.validate_certs:
                cmd.append("--insecure-skip-tls-verify")

            cmd.extend(
                [
                    "-n",
                    namespace,
                    "port-forward",
                    "--address",
                    "127.0.0.1",  # Bind only to localhost
                    f"service/{service}",
                    f"{local_port}:9090",
                ]
            )

            logger.info(f"Starting port-forward for cluster {cluster_id} on port {local_port}")

            # Start port-forward process using async subprocess for non-blocking operation
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Give the process a moment to fail immediately if there's an issue
            await asyncio.sleep(2)

            # Check if process is still running
            if process.returncode is not None:
                # Process exited, get output
                stdout_data, stderr_data = await asyncio.wait_for(process.communicate(), timeout=2.0)
                stderr = stderr_data.decode() if stderr_data else ""
                logger.error(f"Port-forward process died immediately: {stderr}")
                return None

            # Wait for port-forward to be ready
            ready = await self._wait_for_port_forward(local_port)
            if not ready:
                logger.error(f"Port-forward not ready for cluster {cluster_id}")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                return None

            # Store process info
            self.active_forwards[cluster_id] = {
                "process": process,
                "port": local_port,
                "kubeconfig_path": kubeconfig_path,
                "started_at": datetime.utcnow(),
            }

            logger.info(f"Successfully established port-forward for cluster {cluster_id} on port {local_port}")
            return local_port

        except subprocess.TimeoutExpired as e:
            logger.error(f"Command timed out: {e}")
            if process:
                process.kill()
            return None
        except Exception as e:
            logger.error(f"Failed to start port-forward: {e}")
            if process:
                process.terminate()
            return None
        finally:
            # Clean up kubeconfig file if port-forward failed
            if kubeconfig_path and cluster_id not in self.active_forwards:
                try:
                    Path(kubeconfig_path).unlink(missing_ok=True)
                    logger.debug(f"Cleaned up kubeconfig after failed port-forward setup for cluster {cluster_id}")
                except Exception as e:
                    logger.error(
                        f"Failed to clean up kubeconfig {kubeconfig_path} for cluster {cluster_id}: {e}. "
                        "This may leak sensitive credentials!"
                    )

    def _find_available_port(self) -> int:
        """Find an available local port.

        Returns:
            Available port number
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", 0))
            s.listen(1)
            port = s.getsockname()[1]
        return port

    async def _wait_for_port_forward(self, port: int, timeout: int = 30) -> bool:
        """Wait for port-forward to be ready.

        Args:
            port: Local port to check
            timeout: Maximum time to wait in seconds

        Returns:
            True if port is ready, False if timeout
        """
        start_time = time.time()
        attempt_count = 0

        while time.time() - start_time < timeout:
            attempt_count += 1
            try:
                async with (
                    aiohttp.ClientSession() as session,
                    session.get(
                        f"http://localhost:{port}/api/v1/query",
                        params={"query": "up"},
                        timeout=aiohttp.ClientTimeout(total=5),
                    ) as response,
                ):
                    if response.status == 200:
                        logger.debug(f"Port-forward on port {port} is ready after {attempt_count} attempts")
                        return True
                    else:
                        logger.debug(f"Port-forward check returned status {response.status}")
            except aiohttp.ClientError as e:
                logger.debug(f"Port-forward check attempt {attempt_count} failed: {type(e).__name__}")
            except Exception as e:
                logger.debug(f"Unexpected error checking port-forward: {e}")

            # Exponential backoff with max 2 seconds
            await asyncio.sleep(min(0.5 * (1.5 ** (attempt_count - 1)), 2.0))

        logger.warning(f"Port-forward on port {port} not ready after {timeout}s ({attempt_count} attempts)")
        return False

    async def _update_otel_config(
        self,
        cluster_id: str,
        cluster_name: str,
        port: int,
    ):
        """Update OTel Collector configuration for new scrape target.

        This sends configuration to OTel Collector to add a new scrape job.

        Args:
            cluster_id: Cluster identifier
            cluster_name: Cluster name
            port: Local port for Prometheus access
        """
        # For dynamic configuration, we'll send metrics with proper attributes
        # The actual scraping will be handled by our manual process
        # This is because OTel Collector doesn't support dynamic config reload easily

        # Store config for our own scraping
        self.scrape_configs[cluster_id]["port"] = port
        self.scrape_configs[cluster_id]["last_updated"] = datetime.utcnow()

        logger.info(f"Updated scrape config for cluster {cluster_id}: name={cluster_name}, port={port}")

    async def scrape_and_forward_metrics(
        self,
        cluster_id: str,
        queries: List[str],
        duration: timedelta = timedelta(minutes=5),
        step: str = "30s",
    ) -> Tuple[bool, Optional[str]]:
        """Scrape metrics from cluster Prometheus and forward to OTel.

        Args:
            cluster_id: Cluster to scrape from
            queries: List of PromQL queries to execute
            duration: Time range for queries
            step: Query resolution step

        Returns:
            Tuple of (success, error_message)
        """
        if cluster_id not in self.scrape_configs:
            return False, f"Cluster {cluster_id} not configured for scraping"

        config = self.scrape_configs[cluster_id]
        endpoint = config["prometheus_endpoint"]

        try:
            logger.info(f"Starting to scrape {len(queries)} queries from {endpoint} (parallel execution)")

            # Calculate timestamps once for all queries
            start_timestamp = (datetime.utcnow() - duration).timestamp()
            end_timestamp = datetime.utcnow().timestamp()

            async def execute_single_query(session: aiohttp.ClientSession, query: str):
                """Execute a single Prometheus query and return results.

                Returns:
                    List of metric results, or empty list on error
                """
                url = f"{endpoint}/api/v1/query_range"
                params = {
                    "query": query,
                    "start": start_timestamp,
                    "end": end_timestamp,
                    "step": step,
                }

                try:
                    async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data["status"] == "success":
                                result_count = len(data["data"]["result"])
                                if result_count > 0:
                                    logger.debug(f"Query '{query}' returned {result_count} results")
                                    return data["data"]["result"]
                                else:
                                    logger.debug(f"Query '{query}' returned no results")
                                    return []
                        else:
                            response_text = await response.text()
                            logger.warning(
                                f"Query failed for {query}: status={response.status}, response={response_text}"
                            )
                            return []
                except Exception as e:
                    logger.warning(f"Error executing query '{query}': {e}")
                    return []

            async with aiohttp.ClientSession() as session:
                # Execute all queries in parallel using asyncio.gather
                # Use return_exceptions=True to isolate failures
                results = await asyncio.gather(
                    *[execute_single_query(session, query) for query in queries], return_exceptions=True
                )

                # Flatten results and handle exceptions
                metrics_data = []
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.error(f"Query {queries[i]} failed with exception: {result}")
                    elif isinstance(result, list):
                        metrics_data.extend(result)
                    else:
                        logger.warning(f"Unexpected result type for query {queries[i]}: {type(result)}")

            logger.info(f"Scraped total of {len(metrics_data)} metric series from cluster {cluster_id}")

            # Transform and send to OTel
            await self._send_metrics_to_otel(cluster_id, config, metrics_data)

            return True, None

        except Exception as e:
            error_msg = f"Failed to scrape metrics: {e}"
            logger.error(error_msg)
            return False, error_msg

    async def _send_metrics_to_otel(
        self,
        cluster_id: str,
        config: Dict[str, Any],
        metrics_data: List[Dict[str, Any]],
    ):
        """Send scraped metrics to OTel Collector via OTLP.

        Args:
            cluster_id: Cluster identifier
            config: Cluster configuration
            metrics_data: Raw Prometheus metrics data
        """
        if not metrics_data:
            logger.warning(f"No metrics to send for cluster {cluster_id}")
            return

        logger.info(f"Preparing to send {len(metrics_data)} metrics for cluster {cluster_id} to OTel")

        # Prepare metrics batch for OTLP
        otlp_metrics = {
            "resourceMetrics": [
                {
                    "resource": {
                        "attributes": [
                            {"key": "cluster_id", "value": {"stringValue": cluster_id}},
                            {"key": "cluster_name", "value": {"stringValue": config["cluster_name"]}},
                            {"key": "cluster_platform", "value": {"stringValue": config["cluster_platform"]}},
                        ]
                    },
                    "scopeMetrics": [
                        {
                            "scope": {
                                "name": "prometheus",
                                "version": "2.0",
                            },
                            "metrics": self._transform_to_otlp(metrics_data),
                        }
                    ],
                }
            ]
        }

        # Send to OTel Collector with retry logic
        url = f"{self.otel_endpoint}/v1/metrics"
        headers = {
            "Content-Type": "application/json",
            **self.otel_headers,
        }

        # Retry configuration
        max_retries = 5
        base_delay = 1.0  # seconds
        max_delay = 30.0  # seconds

        logger.info(f"Sending metrics to OTel Collector at {url} (with retry)")

        async with aiohttp.ClientSession() as session:
            for attempt in range(max_retries):
                try:
                    async with session.post(
                        url,
                        json=otlp_metrics,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=30),
                    ) as response:
                        response_text = await response.text()
                        if response.status == 200:
                            logger.info(
                                f"Successfully sent {len(metrics_data)} metrics to OTel for cluster {cluster_id}"
                                f"{f' (attempt {attempt + 1})' if attempt > 0 else ''}"
                            )
                            return  # Success!
                        elif response.status >= 500:
                            # Server error - retry
                            logger.warning(
                                f"OTel Collector server error (attempt {attempt + 1}/{max_retries}): "
                                f"status={response.status}, response={response_text}"
                            )
                        elif response.status == 429:
                            # Rate limited - retry
                            logger.warning(f"OTel Collector rate limited (attempt {attempt + 1}/{max_retries})")
                        else:
                            # Client error (4xx) - don't retry
                            logger.error(
                                f"Failed to send metrics to OTel (client error, not retrying): "
                                f"status={response.status}, response={response_text}"
                            )
                            return

                except aiohttp.ClientError as e:
                    logger.warning(f"Network error sending metrics to OTel (attempt {attempt + 1}/{max_retries}): {e}")
                except Exception as e:
                    logger.error(
                        f"Unexpected error sending metrics to OTel (attempt {attempt + 1}/{max_retries}): {e}"
                    )

                # Calculate exponential backoff delay
                if attempt < max_retries - 1:
                    # Exponential backoff: base_delay * 2^attempt, capped at max_delay
                    delay = min(base_delay * (2**attempt), max_delay)
                    logger.info(f"Retrying in {delay:.1f} seconds...")
                    await asyncio.sleep(delay)

            # All retries exhausted
            logger.error(
                f"Failed to send metrics to OTel after {max_retries} attempts for cluster {cluster_id}. "
                "Metrics may be lost."
            )

    def _transform_to_otlp(self, metrics_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Transform Prometheus metrics to OTLP format.

        Args:
            metrics_data: Prometheus query results

        Returns:
            List of OTLP metric records
        """
        otlp_metrics = []

        for metric in metrics_data:
            metric_name = metric["metric"]["__name__"]
            labels = {k: v for k, v in metric["metric"].items() if k != "__name__"}

            # Convert values to OTLP gauge format
            data_points = []
            for timestamp, value in metric["values"]:
                data_points.append(
                    {
                        "timeUnixNano": int(float(timestamp) * 1e9),
                        "asDouble": float(value),
                        "attributes": [{"key": k, "value": {"stringValue": v}} for k, v in labels.items()],
                    }
                )

            otlp_metrics.append(
                {
                    "name": metric_name,
                    "gauge": {
                        "dataPoints": data_points,
                    },
                }
            )

        return otlp_metrics

    async def cleanup_cluster(self, cluster_id: str):
        """Clean up resources for a cluster.

        Robustly terminates port-forward process with timeout-based waiting
        and ensures kubeconfig cleanup with explicit error logging.

        Args:
            cluster_id: Cluster to clean up
        """
        # Stop port-forward if active
        if cluster_id in self.active_forwards:
            info = self.active_forwards[cluster_id]
            process = info["process"]
            pid = process.pid

            logger.info(f"Cleaning up port-forward for cluster {cluster_id} (PID: {pid})")

            # Try graceful termination first
            process.terminate()
            try:
                await asyncio.wait_for(asyncio.to_thread(process.wait), timeout=5.0)
                logger.debug(f"Port-forward process {pid} terminated gracefully")
            except asyncio.TimeoutError:
                # Force kill if termination times out
                logger.warning(f"Port-forward process {pid} did not terminate gracefully, force killing")
                process.kill()
                try:
                    await asyncio.wait_for(asyncio.to_thread(process.wait), timeout=2.0)
                    logger.debug(f"Port-forward process {pid} killed successfully")
                except asyncio.TimeoutError:
                    logger.error(
                        f"Failed to kill port-forward process {pid} for cluster {cluster_id}. "
                        "Process may be a zombie. Manual cleanup may be required."
                    )

            # Verify process is actually dead
            if process.poll() is None:
                logger.error(
                    f"Port-forward process {pid} for cluster {cluster_id} is still running after kill attempts! "
                    "This is a critical issue that may require manual intervention."
                )

            # Clean up kubeconfig file with explicit error logging
            kubeconfig_path = info.get("kubeconfig_path")
            if kubeconfig_path:
                try:
                    Path(kubeconfig_path).unlink(missing_ok=True)
                    logger.debug(f"Cleaned up kubeconfig {kubeconfig_path} for cluster {cluster_id}")
                except Exception as e:
                    logger.error(
                        f"Failed to clean up kubeconfig {kubeconfig_path} for cluster {cluster_id}: {e}. "
                        "This may leak sensitive credentials!"
                    )

            del self.active_forwards[cluster_id]
            logger.info(f"Successfully cleaned up port-forward for cluster {cluster_id}")

        # Remove from scrape configs
        if cluster_id in self.scrape_configs:
            del self.scrape_configs[cluster_id]
            logger.debug(f"Removed scrape config for cluster {cluster_id}")

    async def cleanup_all(self):
        """Clean up all active port-forwards."""
        cluster_ids = list(self.active_forwards.keys())
        for cluster_id in cluster_ids:
            await self.cleanup_cluster(cluster_id)

        logger.info("Cleaned up all active port-forwards")

    def get_active_clusters(self) -> List[Dict[str, Any]]:
        """Get information about active cluster connections.

        Returns:
            List of active cluster configurations
        """
        active = []
        for cluster_id, config in self.scrape_configs.items():
            if cluster_id in self.active_forwards:
                info = self.active_forwards[cluster_id]
                active.append(
                    {
                        "cluster_id": cluster_id,
                        "cluster_name": config["cluster_name"],
                        "port": info["port"],
                        "started_at": info["started_at"].isoformat(),
                        "prometheus_endpoint": config["prometheus_endpoint"],
                    }
                )
        return active
