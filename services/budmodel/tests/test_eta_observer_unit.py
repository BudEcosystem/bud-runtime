import unittest
from unittest.mock import MagicMock, patch
import sys

# Mock missing dependencies
sys.modules["arxiv"] = MagicMock()
sys.modules["git"] = MagicMock()
sys.modules["aria2p"] = MagicMock()
sys.modules["aria2p.downloads"] = MagicMock()
sys.modules["aria2p.api"] = MagicMock()
sys.modules["aria2p.client"] = MagicMock()
sys.modules["json_repair"] = MagicMock()
sys.modules["crawl4ai"] = MagicMock()
sys.modules["crawl4ai.extraction_strategy"] = MagicMock()

from budmodel.model_info.services import ModelExtractionETAObserver, SecurityScanETAObserver
from budmicroframe.commons.schemas import NotificationRequest, NotificationContent
from budmicroframe.commons.constants import WorkflowStatus

class TestETAObserverLazyInit(unittest.TestCase):
    def setUp(self):
        self.workflow_id = "test-workflow-id"
        self.notification_request = MagicMock(spec=NotificationRequest)
        self.notification_request.payload = MagicMock()
        self.notification_request.payload.content = MagicMock(spec=NotificationContent)

    @patch("budmodel.model_info.services.DaprService")
    @patch("budmodel.model_info.services.ModelExtractionService")
    @patch("budmodel.model_info.services.dapr_workflow")
    def test_calculate_eta_lazy_init_success(self, mock_dapr_workflow, mock_extraction_service, mock_dapr_service_cls):
        # Setup mocks
        mock_dapr_service = mock_dapr_service_cls.return_value
        
        # First call returns empty (triggering lazy init), second call returns valid data
        mock_response_empty = MagicMock()
        mock_response_empty.data = None
        
        mock_response_valid = MagicMock()
        mock_response_valid.data = b'{"current_step": "validation", "steps_data": {"validation": {"eta": 10}}}'
        mock_response_valid.json.return_value = {"current_step": "validation", "steps_data": {"validation": {"eta": 10}}}
        
        mock_dapr_service.get_state.side_effect = [mock_response_empty, mock_response_valid]
        
        observer = ModelExtractionETAObserver()
        observer.calculate_eta(
            workflow_id=self.workflow_id,
            notification_request=self.notification_request,
            model_uri="test-uri",
            provider_type="hugging_face",
            hf_token="test-token"
        )
        
        # Verify lazy init was called
        mock_extraction_service.calculate_initial_eta.assert_called_once_with(
            provider_type="hugging_face",
            model_uri="test-uri",
            workflow_id=self.workflow_id,
            hf_token="test-token"
        )
        
        # Verify publish_notification was called (meaning it proceeded to calculate ETA)
        mock_dapr_workflow.publish_notification.assert_called_once()

    @patch("budmodel.model_info.services.DaprService")
    @patch("budmodel.model_info.services.ModelExtractionService")
    def test_calculate_eta_lazy_init_missing_params(self, mock_extraction_service, mock_dapr_service_cls):
        mock_dapr_service = mock_dapr_service_cls.return_value
        mock_response_empty = MagicMock()
        mock_response_empty.data = None
        mock_dapr_service.get_state.return_value = mock_response_empty
        
        observer = ModelExtractionETAObserver()
        observer.calculate_eta(
            workflow_id=self.workflow_id,
            notification_request=self.notification_request,
            # Missing model_uri and provider_type
        )
        
        # Verify lazy init was NOT called
        mock_extraction_service.calculate_initial_eta.assert_not_called()

    @patch("budmodel.model_info.services.DaprService")
    @patch("budmodel.model_info.services.ModelSecurityScanService")
    @patch("budmodel.model_info.services.dapr_workflow")
    def test_security_scan_eta_lazy_init_success(self, mock_dapr_workflow, mock_scan_service, mock_dapr_service_cls):
        mock_dapr_service = mock_dapr_service_cls.return_value
        
        mock_response_empty = MagicMock()
        mock_response_empty.data = None
        
        mock_response_valid = MagicMock()
        mock_response_valid.data = b'{"current_step": "security_scan", "steps_data": {"security_scan": {"eta": 20}}}'
        mock_response_valid.json.return_value = {"current_step": "security_scan", "steps_data": {"security_scan": {"eta": 20}}}
        
        mock_dapr_service.get_state.side_effect = [mock_response_empty, mock_response_valid]
        
        observer = SecurityScanETAObserver()
        observer.calculate_eta(
            workflow_id=self.workflow_id,
            notification_request=self.notification_request,
            model_path="test-path"
        )
        
        # Verify lazy init was called
        mock_scan_service.calculate_initial_eta.assert_called_once_with(
            workflow_id=self.workflow_id,
            model_path="test-path"
        )
        
        # Verify publish_notification was called
        mock_dapr_workflow.publish_notification.assert_called_once()

if __name__ == '__main__':
    unittest.main()
