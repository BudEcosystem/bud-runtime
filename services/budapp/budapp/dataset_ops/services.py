from budapp.commons import logging
from budapp.commons.db_utils import SessionMixin

from .models import DatasetCRUD


logger = logging.get_logger(__name__)


class DatasetService(SessionMixin):
    """Dataset service."""

    async def get_datasets(self, offset, limit, filters_dict, order_by, search):
        """Get all datasets."""
        with DatasetCRUD() as crud:
            return await crud.fetch_many_with_search(offset, limit, filters_dict, order_by, search)
