"""Fallback handler for graceful degradation between NFD and ConfigMap detection."""

import json
from typing import Any, Dict, Union
from uuid import UUID

from budmicroframe.commons.logging import get_logger
from budmicroframe.commons.schemas import ErrorResponse, SuccessResponse

from ..commons.config import app_settings
from .nfd_handler import NFDSchedulableResourceDetector
from .services import ClusterOpsService


logger = get_logger(__name__)


class ResourceDetectionFallbackHandler:
    """Handles fallback between NFD and ConfigMap-based resource detection."""

    @classmethod
    async def get_cluster_info_with_fallback(cls, fetch_cluster_info_request, task_id: str, workflow_id: str) -> str:
        """Get cluster info with automatic fallback to ConfigMap if NFD fails."""
        # Check if NFD detection is enabled
        if not app_settings.enable_nfd_detection:
            logger.info("NFD detection disabled, using ConfigMap method")
            return await ClusterOpsService.fetch_cluster_info(fetch_cluster_info_request, task_id, workflow_id)

        try:
            # Try NFD-enhanced detection first
            logger.info("Attempting NFD-based cluster info detection")
            result = await ClusterOpsService.fetch_cluster_info_enhanced(
                fetch_cluster_info_request, task_id, workflow_id, use_nfd=True
            )

            # Validate NFD result
            if cls._is_valid_nfd_result(result):
                logger.info("NFD detection successful")
                return result
            else:
                logger.warning("NFD result validation failed")
                raise Exception("NFD detection returned invalid data")

        except Exception as e:
            logger.warning(f"NFD detection failed: {e}")

            # NFD is now the only detection method - no fallback to ConfigMap
            # as ConfigMap-based detection is deprecated
            logger.error("NFD detection failed and no fallback is available")
            raise e

    @classmethod
    async def update_node_status_with_fallback(cls, cluster_id: UUID) -> str:
        """Update node status with automatic fallback."""
        # Check if NFD detection is enabled
        if not app_settings.enable_nfd_detection:
            logger.info("NFD detection disabled, using standard node status update")
            return await ClusterOpsService.update_node_status(cluster_id)

        try:
            # Try NFD-enhanced update first
            logger.debug(f"Attempting NFD-based node status update for cluster {cluster_id}")
            result = await ClusterOpsService.update_node_status_enhanced(cluster_id)
            logger.debug(f"NFD node status update successful for cluster {cluster_id}")
            return result

        except Exception as e:
            logger.warning(f"NFD node status update failed for cluster {cluster_id}: {e}")

            # NFD is now the only detection method - no fallback available
            logger.error("NFD-based node status update failed and no fallback is available")
            raise e

    @classmethod
    async def trigger_periodic_update_with_fallback(cls) -> Union[SuccessResponse, ErrorResponse]:
        """Trigger periodic node status updates with fallback handling."""
        try:
            logger.info("Starting periodic node status update with fallback handling")

            # Use the existing trigger method which will use our enhanced methods
            result = await ClusterOpsService.trigger_periodic_node_status_update()

            logger.info("Periodic node status update completed successfully")
            return result

        except Exception as e:
            logger.error(f"Periodic node status update failed: {e}")
            return ErrorResponse(code=500, message=f"Periodic node status update failed: {str(e)}")

    @classmethod
    def _is_valid_nfd_result(cls, result: str) -> bool:
        """Validate NFD detection result."""
        try:
            data = json.loads(result)

            # Check required fields
            required_fields = ["id", "nodes"]
            if not all(field in data for field in required_fields):
                logger.warning("NFD result missing required fields")
                return False

            # Check if nodes have schedulability info
            nodes = data.get("nodes", [])
            if not nodes:
                logger.warning("NFD result has no nodes")
                return False

            # Check if at least one node has NFD-style enhanced info
            has_enhanced_info = any(
                node.get("detection_method") == "nfd" or node.get("nfd_detected") or "schedulable" in node
                for node in nodes
            )

            if not has_enhanced_info:
                logger.warning("NFD result lacks enhanced schedulability information")
                return False

            logger.debug("NFD result validation passed")
            return True

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"NFD result validation failed: {e}")
            return False

    @classmethod
    async def check_nfd_deployment_status(cls, cluster_config: Dict) -> Dict[str, Any]:
        """Check if NFD is properly deployed and functioning in the cluster."""
        try:
            nfd_detector = NFDSchedulableResourceDetector(cluster_config)

            # Try to detect at least one node to verify NFD is working
            nodes = await nfd_detector.get_schedulable_nodes()

            return {"nfd_available": True, "nodes_detected": len(nodes), "error": None}

        except Exception as e:
            logger.warning(f"NFD deployment check failed: {e}")
            return {"nfd_available": False, "nodes_detected": 0, "error": str(e)}

    @classmethod
    def get_detection_method_info(cls) -> Dict[str, Any]:
        """Get information about current detection method configuration."""
        return {
            "nfd_enabled": app_settings.enable_nfd_detection,
            "fallback_enabled": False,  # Deprecated - NFD is now the only method
            "detection_timeout": app_settings.nfd_detection_timeout,
            "nfd_namespace": app_settings.nfd_namespace,
            "primary_method": "nfd" if app_settings.enable_nfd_detection else "configmap",
            "fallback_method": None,  # Deprecated - NFD is now the only method
        }
