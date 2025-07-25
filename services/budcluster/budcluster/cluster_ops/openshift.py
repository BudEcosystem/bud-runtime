from typing import Dict

from budmicroframe.commons.logging import get_logger

from ..commons.exceptions import KubernetesException
from .kubernetes import KubernetesHandler
from .schemas import PlatformEnum


logger = get_logger(__name__)


class OpenshiftHandler(KubernetesHandler):
    """Openshift cluster handler."""

    def __init__(self, config: Dict, ingress_url: str = None):
        """Initialize the OpenshiftHandler with the given configuration and optional ingress URL.

        :param config: Dictionary containing the configuration for the Openshift cluster.
        :param ingress_url: Optional string specifying the ingress URL.
        """
        super().__init__(config, ingress_url)
        self.platform = PlatformEnum.OPENSHIFT

    # def initial_setup(self) -> None:
    #     """Execute initial setup."""
    #     pass

    def apply_security_context(self, namespace: str) -> None:
        """Apply security context to the runtime containers."""
        result = self.ansible_executor.run_playbook(
            playbook="APPLY_SECURITY_CONTEXT",
            extra_vars={"kubeconfig_content": self.config, "namespace": namespace},
        )
        logger.info(result["status"])
        if result["status"] != "successful":
            raise KubernetesException("Failed to deploy runtime")
        return result["status"]

    def get_ingress_url(self, namespace: str) -> str:
        """Get the ingress url for the namespace."""
        ingress_host, schema = self._parse_hostname(self.ingress_url)
        return f"{schema}://{namespace}.{ingress_host}"
