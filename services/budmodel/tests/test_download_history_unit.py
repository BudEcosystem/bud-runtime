import pytest
from unittest.mock import MagicMock, patch
from budmodel.model_info.download_history import DownloadHistory, ModelDownloadStatus, SpaceNotAvailableException
from budmodel.model_info.models import ModelDownloadHistory

@pytest.fixture
def mock_crud():
    with patch("budmodel.model_info.download_history.ModelDownloadHistoryCRUD") as mock:
        yield mock

def test_atomic_space_reservation_new_record(mock_crud):
    mock_session = MagicMock()
    mock_crud.return_value.__enter__.return_value.session = mock_session
    
    # Mock no existing record
    mock_session.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = None
    
    # Mock space check
    mock_session.query.return_value.filter.return_value.scalar.return_value = 0
    
    with patch("budmodel.model_info.download_history.app_settings") as mock_settings:
        mock_settings.model_download_dir_max_size = 1000
        
        result = DownloadHistory.atomic_space_reservation("test_path", 100)
        
        assert result is True
        # Verify insert called
        mock_crud.return_value.__enter__.return_value.insert.assert_called_once()
        args = mock_crud.return_value.__enter__.return_value.insert.call_args[0][0]
        assert args["path"] == "test_path"
        assert args["size"] == 100
        assert args["status"] == ModelDownloadStatus.RUNNING

def test_atomic_space_reservation_existing_running(mock_crud):
    mock_session = MagicMock()
    mock_crud.return_value.__enter__.return_value.session = mock_session
    
    # Mock existing running record
    existing_record = MagicMock()
    existing_record.status = ModelDownloadStatus.RUNNING
    mock_session.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = existing_record
    
    result = DownloadHistory.atomic_space_reservation("test_path", 100)
    
    assert result is True
    # Verify insert NOT called
    mock_crud.return_value.__enter__.return_value.insert.assert_not_called()

def test_atomic_space_reservation_existing_failed(mock_crud):
    mock_session = MagicMock()
    mock_crud.return_value.__enter__.return_value.session = mock_session
    
    # Mock existing failed record
    existing_record = MagicMock()
    existing_record.status = ModelDownloadStatus.FAILED
    mock_session.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = existing_record
    
    # Mock space check (should be called)
    mock_session.query.return_value.filter.return_value.scalar.return_value = 0
    
    with patch("budmodel.model_info.download_history.app_settings") as mock_settings:
        mock_settings.model_download_dir_max_size = 1000
        
        result = DownloadHistory.atomic_space_reservation("test_path", 100)
        
        assert result is True
        # Verify record updated
        assert existing_record.status == ModelDownloadStatus.RUNNING
        assert existing_record.size == 100
        # Verify insert NOT called
        mock_crud.return_value.__enter__.return_value.insert.assert_not_called()
