from typing import Any, Dict, List, Optional, Sequence, Tuple, TypeVar

# from .database import Base
from budmicroframe.commons.logging import get_logger
from budmicroframe.shared.psql_service import PSQLBase
from fastapi import status
from fastapi.exceptions import HTTPException
from sqlalchemy import BigInteger as SqlAlchemyBigInteger
from sqlalchemy import String as SqlAlchemyString
from sqlalchemy import cast, func, inspect, or_, text
from sqlalchemy.dialects.postgresql import ARRAY as PostgresArray
from sqlalchemy.exc import MultipleResultsFound, SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import Executable


logger = get_logger(__name__)


ModelType = TypeVar("ModelType", bound=PSQLBase)  # type: ignore


class SessionMixin:
    """Provides instance of database session."""

    def __init__(self, session: Session) -> None:
        """Initialize session."""
        self.session = session


class DataManagerUtils:
    """Custom validation methods."""

    @staticmethod
    async def validate_fields(model: Any, fields: Dict):
        """Validate fields."""
        for field in fields:
            try:
                _ = getattr(model, field)
            except AttributeError:
                raise ValueError(f"Invalid field: {field} found in model") from None

    @staticmethod
    async def generate_search_stmt(model: Any, fields: Dict):
        """Generate search statement."""
        # Inspect model columns
        model_columns = inspect(model).columns

        # Initialize list to store search conditions
        search_conditions = []

        # Iterate over search fields and generate conditions
        for field, value in fields.items():
            column = getattr(model, field)

            # Check if column type is string like
            if type(model_columns[field].type) is SqlAlchemyString:
                search_conditions.append(func.lower(column).like(f"%{value.lower()}%"))
            elif type(model_columns[field].type) is PostgresArray:
                search_conditions.append(column.contains(value))
            elif type(model_columns[field].type) is SqlAlchemyBigInteger:
                search_conditions.append(cast(column, SqlAlchemyString).like(f"%{value}%"))
            else:
                search_conditions.append(column == value)

        return search_conditions

    @staticmethod
    async def generate_global_search_stmt(model: Any, fields: Dict):
        """Generate global search statement."""
        # Inspect model columns
        _ = inspect(model).columns

        # Initialize list to store search conditions
        search_conditions = []

        # Extract common filters
        is_active = fields.get("is_active", True)
        benchmark = fields.get("benchmark", False)
        search_value = fields.get("name")

        # Add active and benchmark conditions
        search_conditions.append(model.is_active == is_active)
        search_conditions.append(model.benchmark == benchmark)

        # Create conditions for name, description, and tags
        if search_value:
            name_condition = model.name.ilike(f"%{search_value}%")
            description_condition = model.description.ilike(f"%{search_value}%")

            # JSON condition for tags, accessing the "name" key in the JSON structure
            tags_condition = text(
                "EXISTS ("
                "SELECT 1 FROM jsonb_array_elements(CAST(project.tags AS JSONB)) AS tag "
                "WHERE lower(tag->>'name') LIKE :search_value"
                ")"
            ).bindparams(search_value=f"%{search_value.lower()}%")

            # Combine conditions using OR to match name, description, or tags
            search_conditions.append(or_(name_condition, description_condition, tags_condition))

        return search_conditions

    @staticmethod
    async def generate_sorting_stmt(model: Any, sort_details: List[Tuple[str, str]]):
        """Generate sorting statement."""
        sort_conditions = []

        for field, direction in sort_details:
            # Check if column exists, if not, skip
            if field == "tags":
                json_sort_expr = text(f"tags->>'name' {direction.upper()}")
                sort_conditions.append(json_sort_expr)
                continue
            try:
                _ = getattr(model, field)
            except AttributeError:
                continue

            if direction == "asc":
                sort_conditions.append(getattr(model, field))
            else:
                sort_conditions.append(getattr(model, field).desc())

        return sort_conditions


class BaseDataManager(SessionMixin, DataManagerUtils):
    """Base data manager class responsible for operations over database."""

    async def add_one(self, model: ModelType) -> ModelType:
        """Add one model to the database."""
        try:
            self.session.add(model)
            self.session.commit()
            self.session.refresh(model)
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Model creation failed. Error: {str(e)}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=e._message()) from e
        except Exception as e:
            self.session.rollback()
            logger.error(f"Model creation failed. Error: {str(e)}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e

        return model

    async def add_all(self, models: Sequence[ModelType]) -> Sequence[ModelType]:
        """Add all models to the database."""
        try:
            self.session.add_all(models)
            self.session.commit()
            # self.session.refresh(models)
            for model in models:
                self.session.refresh(model)
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Model creation failed. Error: {str(e)}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=e._message()) from e
        except Exception as e:
            self.session.rollback()
            logger.error(f"Model creation failed. Error: {str(e)}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e

        return models

    async def get_one_or_none(self, stmt: Executable) -> Optional[Any]:
        """Get one or none model from the database."""
        try:
            result = self.session.execute(stmt).scalar_one_or_none()
        except MultipleResultsFound as e:
            logger.error(f"Multiple results found. Error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=e._message(),
            ) from e
        except Exception as e:
            logger.error(f"Model retrieval failed. Error: {str(e)}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e

        return result

    async def update_one(self, model: ModelType) -> ModelType:
        """Update one model in the database."""
        try:
            self.session.commit()
            self.session.refresh(model)
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Model update failed. Error: {str(e)}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=e._message()) from e
        except Exception as e:
            self.session.rollback()
            logger.error(f"Model update failed. Error: {str(e)}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e

        return model

    async def delete_one(self, model: ModelType) -> None:
        """Delete one model from the database."""
        try:
            self.session.delete(model)
            self.session.commit()
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Model update failed. Error: {str(e)}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=e._message()) from e
        except Exception as e:
            self.session.rollback()
            logger.error(f"Model update failed. Error: {str(e)}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e

    async def execute_scalar_stmt(self, stmt: Executable) -> Any:
        """Execute scalar statement."""
        try:
            result = self.session.scalar(stmt)
        except SQLAlchemyError as e:
            logger.error(f"Scalar retrieval failed. Error: {str(e)}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=e._message()) from e
        except Exception as e:
            logger.error(f"Scalar retrieval failed. Error: {str(e)}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e

        return result

    async def get_all(self, stmt: Executable, scalar=True) -> Sequence[Any]:
        """Get all models from the database."""
        try:
            results = self.session.scalars(stmt).all() if scalar else self.session.execute(stmt).all()
        except SQLAlchemyError as e:
            logger.error(f"Scalar retrieval failed. Error: {str(e)}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=e._message()) from e
        except Exception as e:
            logger.error(f"Scalar retrieval failed. Error: {str(e)}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e

        return results

    async def execute_commit(self, stmt: Executable) -> None:
        """Execute commit statement."""
        try:
            self.session.execute(stmt)
            self.session.commit()
        except SQLAlchemyError as e:
            logger.error(f"Query execution failed. Error: {str(e)}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=e._message()) from e
        except Exception as e:
            logger.error(f"Query execution failed. Error: {str(e)}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e

    async def delete_all(self, models: Sequence[ModelType]) -> None:
        """Delete all models from the database."""
        try:
            for model in models:
                self.session.delete(model)
            self.session.commit()
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Bulk deletion failed. Error: {str(e)}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=e._message()) from e
        except Exception as e:
            self.session.rollback()
            logger.error(f"Bulk deletion failed. Error: {str(e)}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e
