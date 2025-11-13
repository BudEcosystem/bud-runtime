"""Prometheus client for querying metrics from cluster Prometheus instances."""

import asyncio
import tempfile
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import AsyncGenerator, List, Optional

import aiohttp
import yaml
from budmicroframe.commons.logging import get_logger
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException

from ..commons.config import app_settings
from ..commons.exceptions import KubernetesException
from .schemas import Metric, MetricSample, PrometheusQueryResult


logger = get_logger(__name__)


class PrometheusClient:
    """Client for querying Prometheus instances in Kubernetes clusters."""

    def __init__(self, kubeconfig: str, timeout: int = 30):
        """Initialize Prometheus client.

        Args:
            kubeconfig: Kubernetes configuration as a string
            timeout: Query timeout in seconds
        """
        self.kubeconfig = kubeconfig
        self.timeout = timeout
        self._port_forward_process = None
        self._local_port = None

    @asynccontextmanager
    async def _create_port_forward(self) -> AsyncGenerator[int, None]:
        """Create a port-forward to the Prometheus service.

        Yields:
            Local port number for accessing Prometheus

        Raises:
            KubernetesException: If port-forward fails
        """
        # Write kubeconfig to temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            if isinstance(self.kubeconfig, dict):
                yaml.dump(self.kubeconfig, f)
            else:
                f.write(self.kubeconfig)
            kubeconfig_path = f.name

        try:
            # Load Kubernetes configuration
            config.load_kube_config(config_file=kubeconfig_path)

            # Get the default configuration
            configuration = client.Configuration.get_default_copy()
            # Disable SSL cert validation based on app settings
            configuration.verify_ssl = app_settings.validate_certs
            # Set this configuration as the default
            client.Configuration.set_default(configuration)

            v1 = client.CoreV1Api()

            # Get Prometheus service
            try:
                v1.read_namespaced_service(
                    name=app_settings.prometheus_service_name, namespace=app_settings.prometheus_namespace
                )
            except ApiException as e:
                if e.status == 404:
                    raise KubernetesException(
                        f"Prometheus service {app_settings.prometheus_service_name} not found in namespace {app_settings.prometheus_namespace}"
                    ) from e
                raise KubernetesException(f"Failed to get Prometheus service: {e}") from e

            # Find an available local port
            import socket

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("", 0))
                local_port = s.getsockname()[1]

            # Create port-forward using kubectl command (more reliable than Python API)
            import subprocess

            cmd = [
                "kubectl",
                f"--kubeconfig={kubeconfig_path}",
            ]

            # Add insecure flag if SSL verification is disabled
            if not app_settings.validate_certs:
                cmd.append("--insecure-skip-tls-verify")

            cmd.extend(
                [
                    "port-forward",
                    f"service/{app_settings.prometheus_service_name}",
                    f"{local_port}:{app_settings.prometheus_port}",
                    "-n",
                    app_settings.prometheus_namespace,
                ]
            )

            logger.info(
                f"Creating port-forward from localhost:{local_port} to {app_settings.prometheus_service_name}:{app_settings.prometheus_port}"
            )
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            # Wait for port-forward to be ready
            await asyncio.sleep(2)

            # Check if process is still running
            if process.poll() is not None:
                stderr = process.stderr.read().decode() if process.stderr else ""
                raise KubernetesException(f"Port-forward failed to start: {stderr}")

            self._port_forward_process = process
            self._local_port = local_port

            yield local_port

        finally:
            # Clean up port-forward
            if self._port_forward_process:
                logger.info("Cleaning up port-forward")
                self._port_forward_process.terminate()
                try:
                    self._port_forward_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._port_forward_process.kill()
                self._port_forward_process = None
                self._local_port = None

            # Clean up temporary kubeconfig file
            import os
            from contextlib import suppress

            with suppress(Exception):
                os.unlink(kubeconfig_path)

    async def query(self, query: str, time: Optional[datetime] = None) -> PrometheusQueryResult:
        """Execute an instant query against Prometheus.

        Args:
            query: PromQL query string
            time: Evaluation timestamp (default: now)

        Returns:
            Query result

        Raises:
            Exception: If query fails
        """
        async with self._create_port_forward() as local_port:
            url = f"http://localhost:{local_port}/api/v1/query"
            params = {"query": query}
            if time:
                params["time"] = int(time.timestamp())

            async with aiohttp.ClientSession() as session:
                try:
                    async with session.get(
                        url, params=params, timeout=aiohttp.ClientTimeout(total=self.timeout)
                    ) as response:
                        response.raise_for_status()
                        data = await response.json()
                        return PrometheusQueryResult(**data)
                except aiohttp.ClientError as e:
                    logger.error(f"Failed to query Prometheus: {e}")
                    raise

    async def query_range(
        self, query: str, start: datetime, end: datetime, step: str = "30s"
    ) -> PrometheusQueryResult:
        """Execute a range query against Prometheus.

        Args:
            query: PromQL query string
            start: Start timestamp
            end: End timestamp
            step: Query resolution step (e.g., "30s", "1m")

        Returns:
            Query result with time series data

        Raises:
            Exception: If query fails
        """
        async with self._create_port_forward() as local_port:
            url = f"http://localhost:{local_port}/api/v1/query_range"
            params = {"query": query, "start": int(start.timestamp()), "end": int(end.timestamp()), "step": step}

            async with aiohttp.ClientSession() as session:
                try:
                    async with session.get(
                        url, params=params, timeout=aiohttp.ClientTimeout(total=self.timeout)
                    ) as response:
                        response.raise_for_status()
                        data = await response.json()
                        return PrometheusQueryResult(**data)
                except aiohttp.ClientError as e:
                    logger.error(f"Failed to query Prometheus: {e}")
                    raise

    async def get_metrics(
        self, queries: List[str], duration: timedelta = timedelta(minutes=5), step: str = "30s"
    ) -> List[Metric]:
        """Get metrics for specified queries.

        Args:
            queries: List of PromQL queries
            duration: Time range to query (from now - duration to now)
            step: Query resolution step

        Returns:
            List of metrics with samples

        Raises:
            Exception: If any query fails
        """
        metrics = []
        end_time = datetime.utcnow()
        start_time = end_time - duration

        # Create a single port-forward for all queries
        async with self._create_port_forward() as local_port:
            url = f"http://localhost:{local_port}/api/v1/query_range"

            async with aiohttp.ClientSession() as session:
                for query in queries:
                    try:
                        logger.debug(f"Executing query: {query}")

                        params = {
                            "query": query,
                            "start": int(start_time.timestamp()),
                            "end": int(end_time.timestamp()),
                            "step": step,
                        }

                        async with session.get(
                            url, params=params, timeout=aiohttp.ClientTimeout(total=self.timeout)
                        ) as response:
                            response.raise_for_status()
                            data = await response.json()
                            result = PrometheusQueryResult(**data)

                            if result.status != "success":
                                logger.warning(f"Query {query} returned status: {result.status}")
                                continue

                            # Parse result and create metrics
                            if result.data.get("resultType") == "matrix":
                                for series in result.data.get("result", []):
                                    metric_name = series.get("metric", {}).get("__name__", query)
                                    labels = {k: v for k, v in series.get("metric", {}).items() if k != "__name__"}

                                    metric = Metric(
                                        name=metric_name,
                                        labels=labels,
                                        samples=[
                                            MetricSample(timestamp=ts, value=float(val))
                                            for ts, val in series.get("values", [])
                                        ],
                                    )
                                    metrics.append(metric)

                    except aiohttp.ClientError as e:
                        logger.error(f"Failed to execute query {query}: {e}")
                        # Continue with other queries even if one fails
                    except Exception as e:
                        logger.error(f"Failed to execute query {query}: {e}")
                        # Continue with other queries even if one fails

        return metrics

    async def test_connection(self) -> bool:
        """Test connection to Prometheus.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Try a simple query to test connection
            result = await self.query("up")
            return result.status == "success"
        except Exception as e:
            logger.error(f"Prometheus connection test failed: {e}")
            return False
