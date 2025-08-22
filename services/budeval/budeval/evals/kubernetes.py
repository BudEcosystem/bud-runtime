from budmicroframe.commons.logging import logging

from budeval.evals.base import BaseClusterHandler
from budeval.evals.schemas import StartEvaluationRequest
from budeval.registry.orchestrator.ansible_orchestrator import AnsibleOrchestrator


logger = logging.getLogger(__name__)


class KubernetesClusterHandler(BaseClusterHandler):
    """Kubernetes cluster handler."""

    def verify_cluster_connection(self, kubeconfig: str) -> bool:
        """Verify cluster connection."""
        try:
            logger.info(f"Verifying cluster connection for kubeconfig: {kubeconfig}")
            ansible_runner = AnsibleOrchestrator()
            return ansible_runner.verify_cluster_connection(kubeconfig)
        except Exception as e:
            logger.error(f"Error verifying cluster connection: {e}")
            return False

    def evaluate_model(self, evaluate_model_request: StartEvaluationRequest) -> bool:
        """Evaluate model."""
        try:
            ansible_runner = AnsibleOrchestrator()
            return ansible_runner.evaluate_model(evaluate_model_request)
        except Exception as e:
            logger.error(f"Error evaluating model: {e}")
            return False
