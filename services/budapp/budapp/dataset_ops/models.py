from typing import Dict, List, Optional
from uuid import UUID, uuid4

from budmicroframe.shared.psql_service import CRUDMixin, PSQLBase, TimestampMixin
from sqlalchemy import (
    Boolean,
    Enum,
    Integer,
    String,
    Uuid,
    and_,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..commons.constants import DatasetStatusEnum


class DatasetSchema(PSQLBase, TimestampMixin):
    """Dataset model schema."""

    __tablename__ = "dataset"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=True)
    description: Mapped[str] = mapped_column(String, nullable=True)
    tags: Mapped[dict] = mapped_column(JSONB, nullable=True)
    hf_hub_url: Mapped[str] = mapped_column(String, nullable=True)
    ms_hub_url: Mapped[str] = mapped_column(String, nullable=True)
    script_url: Mapped[int] = mapped_column(String, nullable=True)
    file_name: Mapped[str] = mapped_column(String, nullable=True)
    formatting: Mapped[str] = mapped_column(String, nullable=True)
    ranking: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    subset: Mapped[str] = mapped_column(String, nullable=True)
    split: Mapped[str] = mapped_column(String, nullable=True)
    folder: Mapped[str] = mapped_column(String, nullable=True)
    num_samples: Mapped[int] = mapped_column(Integer, nullable=True)
    columns: Mapped[dict] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum(
            DatasetStatusEnum,
            name="dataset_status_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=DatasetStatusEnum.ACTIVE,
    )


class DatasetCRUD(CRUDMixin[DatasetSchema, None, None]):
    __model__ = DatasetSchema

    def __init__(self):
        """Initialize dataset crud methods."""
        super().__init__(model=self.__model__)

    async def fetch_many_with_search(
        self,
        offset: int = 0,
        limit: int = 10,
        filters: Optional[Dict] = None,
        order_by: Optional[List] = None,
        search: bool = False,
    ):
        """Fetch many with search."""
        filters = filters or {}
        order_by = order_by or []

        await self.validate_fields(self.model, filters)

        if search:
            search_conditions = []
            search_conditions.extend(await self.generate_search_stmt(self.model, filters))

            stmt = select(self.model).filter(and_(*search_conditions))
            count_stmt = select(func.count()).select_from(self.model).filter(and_(*search_conditions))
        else:
            stmt = select(self.model)
            count_stmt = select(func.count()).select_from(self.model)
            for key, value in filters.items():
                stmt = stmt.filter(getattr(self.model, key) == value)
                count_stmt = count_stmt.filter(getattr(self.model, key) == value)

        # Calculate count before applying limit and offset
        count = self.execute_scalar(count_stmt)

        # Apply limit and offset
        stmt = stmt.limit(limit).offset(offset)

        # Apply sorting
        if order_by:
            sort_conditions = await self.generate_sorting_stmt(self.model, order_by)
            # Extend sort conditions with explicit conditions
            stmt = stmt.order_by(*sort_conditions)

        print(stmt)

        result = self.scalars_all(stmt)

        return result, count

    async def get_datatsets_by_ids(self, ids: List[UUID]):
        """Get datasets by ids."""
        stmt = select(self.model).filter(self.model.id.in_(ids))
        return self.scalars_all(stmt)
