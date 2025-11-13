"""Unit tests for metrics collector module."""

import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from budcluster.commons.constants import ClusterStatusEnum
from budcluster.metrics_collector.metrics_service import MetricsCollectionService
from budcluster.metrics_collector.prometheus_client import PrometheusClient
from budcluster.metrics_collector.schemas import (
    Metric,
    MetricSample,
    MetricsCollectionResult,
    MetricsCollectionStatus,
    PrometheusQueryResult,
)


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    session = AsyncMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


@pytest.fixture
def mock_cluster():
    """Create a mock cluster object."""
    cluster = Mock()
    cluster.id = "test-cluster-id"
    cluster.name = "test-cluster"
    cluster.platform = "kubernetes"
    cluster.status = ClusterStatusEnum.ACTIVE
    cluster.configuration = "encrypted-kubeconfig"
    cluster.last_metrics_collection = None
    cluster.metrics_collection_status = None
    return cluster


@pytest.fixture
def sample_metrics():
    """Create sample metrics for testing."""
    return [
        Metric(
            name="node_cpu_seconds_total",
            labels={"instance": "node1", "cpu": "0"},
            samples=[
                MetricSample(timestamp=time.time(), value=100.0),
                MetricSample(timestamp=time.time() + 30, value=110.0),
            ]
        ),
        Metric(
            name="node_memory_MemAvailable_bytes",
            labels={"instance": "node1"},
            samples=[
                MetricSample(timestamp=time.time(), value=8589934592),
            ]
        ),
    ]


class TestPrometheusClient:
    """Test Prometheus client functionality."""

    @pytest.mark.asyncio
    async def test_query_success(self):
        """Test successful Prometheus query."""
        client = PrometheusClient("test-kubeconfig", timeout=30)

        with patch.object(client, "_create_port_forward") as mock_port_forward:
            mock_port_forward.return_value.__aenter__ = AsyncMock(return_value=8080)
            mock_port_forward.return_value.__aexit__ = AsyncMock()

            with patch("aiohttp.ClientSession") as mock_session:
                mock_response = AsyncMock()
                mock_response.status = 200
                mock_response.raise_for_status = Mock()
                mock_response.json = AsyncMock(return_value={
                    "status": "success",
                    "data": {
                        "resultType": "vector",
                        "result": []
                    }
                })

                mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response

                result = await client.query("up")

                assert result.status == "success"
                assert result.data["resultType"] == "vector"

    @pytest.mark.asyncio
    async def test_get_metrics(self):
        """Test getting metrics from Prometheus."""
        client = PrometheusClient("test-kubeconfig", timeout=30)

        with patch.object(client, "query_range") as mock_query_range:
            mock_query_range.return_value = PrometheusQueryResult(
                status="success",
                data={
                    "resultType": "matrix",
                    "result": [
                        {
                            "metric": {"__name__": "test_metric", "instance": "test"},
                            "values": [[1234567890, "100"], [1234567920, "110"]]
                        }
                    ]
                }
            )

            metrics = await client.get_metrics(["test_metric"], timedelta(minutes=5))

            assert len(metrics) == 1
            assert metrics[0].name == "test_metric"
            assert metrics[0].labels["instance"] == "test"
            assert len(metrics[0].samples) == 2

    @pytest.mark.asyncio
    async def test_test_connection(self):
        """Test connection testing."""
        client = PrometheusClient("test-kubeconfig", timeout=30)

        with patch.object(client, "query") as mock_query:
            mock_query.return_value = PrometheusQueryResult(
                status="success",
                data={"resultType": "vector", "result": []}
            )

            assert await client.test_connection() is True

            mock_query.side_effect = Exception("Connection failed")
            assert await client.test_connection() is False


class TestMetricsCollectionService:
    """Test metrics collection service."""

    @pytest.mark.asyncio
    async def test_collect_all_clusters_metrics(self, mock_session, mock_cluster, sample_metrics):
        """Test collecting metrics from all clusters."""
        service = MetricsCollectionService(mock_session)

        # Mock get_clusters
        with patch("budcluster.metrics_collector.metrics_service.get_clusters") as mock_get_clusters:
            mock_get_clusters.return_value = [mock_cluster]

            # Mock collect_cluster_metrics
            with patch.object(service, "collect_cluster_metrics") as mock_collect:
                mock_collect.return_value = Mock(
                    cluster_id="test-cluster-id",
                    cluster_name="test-cluster",
                    status=MetricsCollectionStatus.SUCCESS,
                    metrics_count=2,
                    error=None
                )

                result = await service.collect_all_clusters_metrics()

                assert isinstance(result, MetricsCollectionResult)
                assert result.total_clusters == 1
                assert result.successful == 1
                assert result.failed == 0
                assert result.skipped == 0

    @pytest.mark.asyncio
    async def test_collect_cluster_metrics_success(self, mock_session, mock_cluster, sample_metrics):
        """Test successful metrics collection from a single cluster."""
        service = MetricsCollectionService(mock_session)

        # Mock crypto
        mock_crypto = Mock()
        mock_crypto.decrypt = Mock(return_value="decrypted-kubeconfig")
        service.crypto = mock_crypto

        with patch("budcluster.metrics_collector.metrics_service.get_cluster_by_id") as mock_get_cluster:
            mock_get_cluster.return_value = mock_cluster

            with patch("budcluster.metrics_collector.metrics_service.PrometheusClient") as mock_prom_class:
                mock_prom_client = AsyncMock()
                mock_prom_client.test_connection = AsyncMock(return_value=True)
                mock_prom_client.get_metrics = AsyncMock(return_value=sample_metrics)
                mock_prom_class.return_value = mock_prom_client

                result = await service.collect_cluster_metrics("test-cluster-id")

                assert result.status == MetricsCollectionStatus.SUCCESS
                assert result.metrics_count == len(sample_metrics)
                assert result.cluster_id == "test-cluster-id"

    @pytest.mark.asyncio
    async def test_collect_cluster_metrics_prometheus_failure(self, mock_session, mock_cluster):
        """Test handling of Prometheus connection failure."""
        service = MetricsCollectionService(mock_session)

        # Mock crypto
        mock_crypto = Mock()
        mock_crypto.decrypt = Mock(return_value="decrypted-kubeconfig")
        service.crypto = mock_crypto

        with patch("budcluster.metrics_collector.metrics_service.get_cluster_by_id") as mock_get_cluster:
            mock_get_cluster.return_value = mock_cluster

            with patch("budcluster.metrics_collector.metrics_service.PrometheusClient") as mock_prom_class:
                mock_prom_client = AsyncMock()
                mock_prom_client.test_connection = AsyncMock(return_value=False)
                mock_prom_class.return_value = mock_prom_client

                result = await service.collect_cluster_metrics("test-cluster-id")

                assert result.status == MetricsCollectionStatus.FAILED
                assert "Failed to connect to Prometheus" in result.error

    @pytest.mark.asyncio
    async def test_collect_cluster_metrics_inactive_cluster(self, mock_session, mock_cluster):
        """Test skipping inactive clusters."""
        service = MetricsCollectionService(mock_session)

        mock_cluster.status = ClusterStatusEnum.DELETED

        with patch("budcluster.metrics_collector.metrics_service.get_cluster_by_id") as mock_get_cluster:
            mock_get_cluster.return_value = mock_cluster

            result = await service.collect_cluster_metrics("test-cluster-id")

            assert result.status == MetricsCollectionStatus.SKIPPED
            assert "Cluster status is" in result.error

    @pytest.mark.asyncio
    async def test_metrics_collection_disabled_globally(self, mock_session):
        """Test when metrics collection is disabled globally."""
        service = MetricsCollectionService(mock_session)

        with patch("budcluster.metrics_collector.metrics_service.app_settings") as mock_settings:
            mock_settings.get.return_value = "false"

            result = await service.collect_all_clusters_metrics()

            assert result.total_clusters == 0
            assert result.successful == 0
            assert result.duration_seconds == 0
