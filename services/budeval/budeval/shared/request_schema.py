from typing import Optional

from pydantic import BaseModel


class DatasetFilter(BaseModel):
    engine_name: Optional[str] = None
    dataset_name: Optional[str] = None
    arc: Optional[str] = None
    config_path: Optional[str] = None


class PaginationParams(BaseModel):
    page: int = 1
    page_size: int = 10
    sort_by: Optional[str] = None
    sort_order: Optional[str] = "asc"  # or "desc"
