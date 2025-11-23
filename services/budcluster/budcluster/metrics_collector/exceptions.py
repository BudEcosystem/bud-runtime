"""Custom exceptions for metrics collection."""


class NamespaceNotFoundError(Exception):
    """Raised when expected namespace is not found in cluster."""

    pass


class PrometheusServiceNotFoundError(Exception):
    """Raised when Prometheus service is not found in expected namespace."""

    pass
