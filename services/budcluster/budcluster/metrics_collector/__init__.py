"""Metrics collection module for pulling metrics from cluster Prometheus instances and forwarding to OTel Collector."""

from .metrics_service import MetricsCollectionService
from .prometheus_client import PrometheusClient


__all__ = ["PrometheusClient", "MetricsCollectionService"]
