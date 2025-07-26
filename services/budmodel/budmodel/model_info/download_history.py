from sqlalchemy import func

from ..commons.config import app_settings
from ..commons.constants import ModelDownloadStatus
from .models import ModelDownloadHistory, ModelDownloadHistoryCRUD


class DownloadHistory:
    @staticmethod
    def create_download_history(path, size):
        with ModelDownloadHistoryCRUD() as crud:
            return crud.insert(
                {
                    "path": path,
                    "size": size,
                    "status": ModelDownloadStatus.RUNNING,
                },
                raise_on_error=True,
            )

    @staticmethod
    def update_download_status(path: str, status: ModelDownloadStatus):
        with ModelDownloadHistoryCRUD() as crud:
            crud.update({"status": status}, conditions={"path": path}, raise_on_error=True)

    @staticmethod
    def delete_download_history(path):
        with ModelDownloadHistoryCRUD() as crud:
            crud.delete(conditions={"path": path}, raise_on_error=False)

    @staticmethod
    def get_total_space_usage():
        with ModelDownloadHistoryCRUD() as crud:
            return crud.session.query(func.sum(ModelDownloadHistory.size)).scalar() or 0

    @staticmethod
    def get_available_space():
        used_space = DownloadHistory.get_total_space_usage()
        return app_settings.model_download_dir_max_size - used_space
