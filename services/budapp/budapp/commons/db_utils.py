#  -----------------------------------------------------------------------------
#  Copyright (c) 2024 Bud Ecosystem Inc.
#  #
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#  #
#      http://www.apache.org/licenses/LICENSE-2.0
#  #
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#  -----------------------------------------------------------------------------

"""Provides utility functions for managing database operations."""

from typing import Any, Dict, List, Optional, Tuple, Type

from fastapi import status
from sqlalchemy import BigInteger as SqlAlchemyBigInteger
from sqlalchemy import String as SqlAlchemyString
from sqlalchemy import cast, delete, func, inspect, select
from sqlalchemy.dialects.postgresql import ARRAY as PostgresArray
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session
from sqlalchemy.sql import Executable

from . import logging
from .exceptions import ClientException, DatabaseException


logger = logging.get_logger(__name__)


class SessionMixin:
    """A mixin class that provides an instance of a database session.

    This mixin is designed to be used with classes that require database access.
    It initializes and stores a SQLAlchemy Session object for database operations.

    Attributes:
        session (Session): An instance of SQLAlchemy Session for database operations.

    Example:
        class MyDatabaseHandler(SessionMixin):
            def __init__(self, session):
                super().__init__(session)

            def some_db_operation(self):
                # Use self.session to perform database operations
                pass
    """

    def __init__(self, session: Session) -> None:
        """Initialize the SessionMixin with a database session.

        Args:
            session (Session): An instance of SQLAlchemy Session to be used for database operations.
        """
        self.session = session


class SQLAlchemyMixin(SessionMixin):
    """A mixin class that provides methods for database operations."""

    def add_one(self, model: object) -> object:
        """Add a single model instance to the database.

        This method adds the given model to the session, commits the transaction,
        and refreshes the model to ensure it reflects the current state in the database.

        Args:
            model (Any): The SQLAlchemy model instance to be added to the database.

        Returns:
            Any: The added and refreshed model instance.

        Raises:
            DatabaseException: If there's an error during the database operation.
        """
        try:
            self.session.add(model)
            self.session.commit()
            self.session.refresh(model)
            return model
        except (Exception, SQLAlchemyError) as e:
            self.session.rollback()
            logger.exception(f"Failed to add one model to database: {e}")
            raise DatabaseException("Unable to add model to database") from e

    def add_all(self, models: List[object]) -> List[object]:
        """Add a list of model instances to the database.

        This method adds the given model to the session, commits the transaction,
        and refreshes the model to ensure it reflects the current state in the database.

        Args:
            models (List[Any]): The SQLAlchemy model instances to be added to the database.

        Returns:
            Any: The added and refreshed model instance.

        Raises:
            DatabaseException: If there's an error during the database operation.
        """
        try:
            self.session.add_all(models)
            self.session.commit()
            return models
        except (Exception, SQLAlchemyError) as e:
            self.session.rollback()
            logger.exception(f"Failed to add all models to database: {e}")
            raise DatabaseException("Unable to add models to database") from e

    def scalar_one_or_none(self, stmt: Executable) -> object:
        """Execute a SQL statement and return a single result or None.

        This method executes the given SQL statement and returns either a single
        scalar result or None if no results are found.

        Args:
            stmt (Executable): The SQLAlchemy statement to be executed.

        Returns:
            Any: The scalar result of the query, or None if no results are found.

        Raises:
            DatabaseException: If there's an error during the database operation.
        """
        try:
            return self.session.execute(stmt).scalar_one_or_none()
        except (Exception, SQLAlchemyError) as e:
            self.session.rollback()  # Ensure rollback on error
            logger.exception(f"Failed to get one model from database: {e}")
            raise DatabaseException("Unable to get model from database") from e

    def update_one(self, model: object) -> object:
        """Update a single model instance in the database.

        This method commits the current session (which should contain the updates to the model),
        and then refreshes the model to ensure it reflects the current state in the database.

        Args:
            model (Any): The SQLAlchemy model instance to be updated in the database.

        Returns:
            Any: The updated and refreshed model instance.

        Raises:
            DatabaseException: If there's an error during the database operation.
        """
        try:
            self.session.commit()
            self.session.refresh(model)
            return model
        except (Exception, SQLAlchemyError) as e:
            self.session.rollback()
            logger.exception(f"Failed to update one model in database: {e}")
            raise DatabaseException("Unable to update model in database") from e

    def delete_model(self, model: object) -> None:
        """Delete a single model instance from the database.

        This method commits the current session, and then deletes the model from the database.

        Args:
            model (Any): The SQLAlchemy model instance to be deleted from the database.

        Raises:
            DatabaseException: If there's an error during the database operation.
        """
        try:
            self.session.delete(model)
            self.session.commit()
        except (Exception, SQLAlchemyError) as e:
            self.session.rollback()
            logger.exception(f"Failed to delete one model in database: {e}")
            raise DatabaseException("Unable to delete model in database") from e

    def scalars_all(self, stmt: Executable) -> object:
        """Scalars a SQL statement and return a single result or None.

        This method executes the given SQL statement and returns the result.

        Args:
            stmt (Executable): The SQLAlchemy statement to be executed.

        Returns:
            Any: The result of the executed statement.

        Raises:
            DatabaseException: If there's an error during the database operation.
        """
        try:
            return self.session.scalars(stmt).all()
        except (Exception, SQLAlchemyError) as e:
            self.session.rollback()  # Ensure rollback on error
            logger.exception(f"Failed to execute statement: {e}")
            raise DatabaseException("Unable to execute statement") from e

    def execute_all(self, stmt: Executable) -> object:
        """Execute a SQL statement and return a single result or None.

        This method executes the given SQL statement and returns the result.

        Args:
            stmt (Executable): The SQLAlchemy statement to be executed.

        Returns:
            Any: The result of the executed statement.

        Raises:
            DatabaseException: If there's an error during the database operation.
        """
        try:
            return self.session.execute(stmt).all()
        except (Exception, SQLAlchemyError) as e:
            self.session.rollback()  # Ensure rollback on error
            logger.exception(f"Failed to execute statement: {e}")
            raise DatabaseException("Unable to execute statement") from e

    def execute_scalar(self, stmt: Executable) -> object:
        """Execute a SQL statement and return a single result or None.

        This method executes the given SQL statement and returns the result.

        Args:
            stmt (Executable): The SQLAlchemy statement to be executed.

        Returns:
            Any: The result of the executed statement.

        Raises:
            DatabaseException: If there's an error during the database operation.
        """
        try:
            return self.session.scalar(stmt)
        except (Exception, SQLAlchemyError) as e:
            self.session.rollback()  # Ensure rollback on error
            logger.exception(f"Failed to execute scalar statement: {e}")
            raise DatabaseException("Unable to execute scalar statement") from e

    async def execute_commit(self, stmt: Executable) -> None:
        try:
            self.session.execute(stmt)
            self.session.commit()
        except (Exception, SQLAlchemyError) as e:
            self.session.rollback()  # Ensure rollback on error
            logger.exception(f"Failed to execute statement: {e}")
            raise DatabaseException("Unable to execute statement") from e


class DataManagerUtils(SQLAlchemyMixin):
    """Utility class for data management operations."""

    @staticmethod
    async def validate_fields(model: Type[DeclarativeBase], fields: Dict[str, Any]) -> None:
        """Validate that the given fields exist in the SQLAlchemy model.

        Args:
            model (Type[DeclarativeBase]): The SQLAlchemy model class to validate against.
            fields (Dict[str, Any]): A dictionary of field names and their values to validate.

        Raises:
            DatabaseException: If an invalid field is found in the input.
        """
        for field in fields:
            if not hasattr(model, field):
                logger.error(f"Invalid field: '{field}' not found in {model.__name__} model")
                raise DatabaseException(f"Invalid field: '{field}' not found in {model.__name__} model")

    @staticmethod
    async def generate_search_stmt(model: Type[DeclarativeBase], fields: Dict[str, Any]) -> List[Executable]:
        """Generate search conditions for a SQLAlchemy model based on the provided fields.

        Args:
            model (Type[DeclarativeBase]): The SQLAlchemy model class to generate search conditions for.
            fields (Dict): A dictionary of field names and their values to search by.

        Returns:
            List[Executable]: A list of SQLAlchemy search conditions.
        """
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
    async def generate_sorting_stmt(
        model: Type[DeclarativeBase], sort_details: List[Tuple[str, str]]
    ) -> List[Executable]:
        """Generate sorting conditions for a SQLAlchemy model based on the provided sort details.

        Args:
            model (Type[DeclarativeBase]): The SQLAlchemy model class to generate sorting conditions for.
            sort_details (List[Tuple[str, str]]): A list of tuples, where each tuple contains a field name and a direction ('asc' or 'desc').

        Returns:
            List[Executable]: A list of SQLAlchemy sorting conditions.
        """
        sort_conditions = []

        for field, direction in sort_details:
            # Check if column exists, if not, skip
            try:
                getattr(model, field)
            except AttributeError:
                continue

            if direction == "asc":
                sort_conditions.append(getattr(model, field))
            else:
                sort_conditions.append(getattr(model, field).desc())

        return sort_conditions

    async def insert_one(self, model: object) -> object:
        """Insert a single model instance into the database.

        This method is an alias for the `add_one` method, providing a more
        intuitive name for the insertion operation.

        Args:
            model (object): The model instance to be inserted into the database.

        Returns:
            object: The inserted model instance, potentially with updated
                attributes (e.g., auto-generated ID).

        Raises:
            Any exceptions that may be raised by the underlying `add_one` method.
        """
        return self.add_one(model)

    async def insert_all(self, models: List[object]) -> List[object]:
        """Insert a list of model instances into the database.

        This method is an alias for the `add_all` method, providing a more
        intuitive name for the insertion operation.

        Args:
            models (List[object]): The list of model instances to be inserted into the database.

        Returns:
            List[object]: The list of inserted model instances.
        """
        return self.add_all(models)

    async def retrieve_by_fields(
        self,
        model: Type[DeclarativeBase],
        fields: Dict[str, Any],
        exclude_fields: Optional[Dict[str, Any]] = None,
        missing_ok: bool = False,
        case_sensitive: bool = True,
    ) -> Optional[DeclarativeBase]:
        """Retrieve a model instance from the database based on given fields.

        This method queries the database for a model instance matching the provided fields.
        If the instance is not found and missing_ok is False, it raises an HTTPException.

        Args:
            model (Type[DeclarativeBase]): The SQLAlchemy model class to query.
            fields (Dict): A dictionary of field names and their values to filter by.
            missing_ok (bool, optional): If True, return None when no instance is found
                                         instead of raising an exception. Defaults to False.
            case_sensitive (bool, optional): If True, the search will be case-sensitive.
                                             Defaults to True.
            exclude_fields (Optional[Dict[str, Any]]): A dictionary of field names and values to exclude from the results.

        Returns:
            Optional[DeclarativeBase]: The found model instance, or None if not found and missing_ok is True.

        Raises:
            HTTPException: If the model instance is not found and missing_ok is False.
            DatabaseException: If there's an error in field validation or database operation.
        """
        await self.validate_fields(model, fields)

        # Build main query
        if case_sensitive:
            stmt = select(model).filter_by(**fields)
        else:
            conditions = []
            for field_name, value in fields.items():
                field = getattr(model, field_name)
                if isinstance(field.type, SqlAlchemyString):
                    # NOTE: didn't use ilike because of escape character issue
                    conditions.append(func.lower(cast(field, SqlAlchemyString)) == func.lower(value))
                else:
                    conditions.append(field == value)
            stmt = select(model).filter(*conditions)

        if exclude_fields is not None:
            await self.validate_fields(model, exclude_fields)
            exclude_conditions = []
            for field_name, value in exclude_fields.items():
                field = getattr(model, field_name)
                if not case_sensitive and isinstance(field.type, SqlAlchemyString):
                    exclude_conditions.append(func.lower(cast(field, SqlAlchemyString)) != func.lower(value))
                else:
                    exclude_conditions.append(field != value)
            stmt = stmt.filter(*exclude_conditions)

        db_model = self.scalar_one_or_none(stmt)

        if not missing_ok and db_model is None:
            logger.info(f"{model.__name__} not found in database")
            raise ClientException(f"{model.__name__} not found", status_code=status.HTTP_404_NOT_FOUND)

        return db_model if db_model else None

    async def update_by_fields(self, model: Type[DeclarativeBase], fields: Dict[str, Any]) -> object:
        """Update a model instance with the given fields.

        This method updates the attributes of the provided model instance with the values
        in the fields dictionary and then persists the changes to the database.

        Args:
            model (Type[DeclarativeBase]): The SQLAlchemy model instance to update.
            fields (Dict): A dictionary of field names and their new values.

        Returns:
            DeclarativeBase: The updated model instance.

        Raises:
            DatabaseException: If there's an error in field validation or database operation.
        """
        await self.validate_fields(model, fields)

        for field, value in fields.items():
            setattr(model, field, value)

        return self.update_one(model)

    async def delete_one(self, model: Type[DeclarativeBase]) -> None:
        """Delete a model instance from the database."""
        self.delete_model(model)

    async def delete_by_fields(self, model: Type[DeclarativeBase], fields: Dict[str, Any]) -> None:
        """Delete a model instance from the database based on the given fields.

        This method deletes the model instance from the database based on the provided fields.
        If the instance is not found and missing_ok is False, it raises an HTTPException.

        Args:
            model (Type[DeclarativeBase]): The SQLAlchemy model class to delete.
            fields (Dict): A dictionary of field names and their values to filter by.

        Raises:
            DatabaseException: If there's an error in field validation or database operation.
        """
        await self.validate_fields(model, fields)

        stmt = delete(model).filter_by(**fields)

        self.session.execute(stmt)
        self.session.commit()

    async def get_all_by_fields(
        self, model: Type[DeclarativeBase], fields: Dict[str, Any], exclude_fields: Optional[Dict[str, Any]] = None
    ) -> Optional[List[DeclarativeBase]]:
        """Retrieve all model instances from database based on the given fields.

        This method queries the database for all model instances matching the provided fields.
        If no instances are found and missing_ok is False, it raises an HTTPException.

        Args:
            model (Type[DeclarativeBase]): The SQLAlchemy model class to query.
            fields (Dict): A dictionary of field names and their values to filter by.
            exclude_fields (Optional[Dict[str, Any]]): A dictionary of field names and values to exclude from the results.

        Returns:
            Optional[List[DeclarativeBase]]: A list of found model instances, or an empty list if not found
                                            and missing_ok is True.

        Raises:
            HTTPException: If no model instances are found and missing_ok is False.
            DatabaseException: If there's an error in field validation or database operation.
        """
        await self.validate_fields(model, fields)

        stmt = select(model).filter_by(**fields)

        if exclude_fields is not None:
            await self.validate_fields(model, exclude_fields)
            exclude_conditions = [getattr(model, field) != value for field, value in exclude_fields.items()]
            stmt = stmt.filter(*exclude_conditions)

        return self.scalars_all(stmt)

    async def get_count_by_fields(
        self, model: Type[DeclarativeBase], fields: Dict[str, Any], exclude_fields: Optional[Dict[str, Any]] = None
    ) -> int:
        """Get the count of model instances from database based on the given fields.

        Args:
            model (Type[DeclarativeBase]): The SQLAlchemy model class to query.
            fields (Dict): A dictionary of field names and their values to filter by.
            exclude_fields (Optional[Dict[str, Any]]): A dictionary of field names and values to exclude from the results.

        Returns:
            int: The count of model instances matching the provided fields.
        """
        await self.validate_fields(model, fields)

        stmt = select(func.count()).select_from(model).filter_by(**fields)

        if exclude_fields:
            await self.validate_fields(model, exclude_fields)
            exclude_conditions = [getattr(model, field) != value for field, value in exclude_fields.items()]
            stmt = stmt.filter(*exclude_conditions)

        return self.execute_scalar(stmt)

    async def upsert_one(
        self, model: Type[DeclarativeBase], fields: Dict[str, Any], conflict_target: List[str]
    ) -> object:
        """Upsert a model instance into the database.

        This method upserts a model instance into the database based on the provided fields.
        If the instance already exists, it updates the existing instance with the new values.
        Otherwise, it inserts a new instance.

        Args:
            model (Type[DeclarativeBase]): The SQLAlchemy model class to upsert.
            fields (Dict): A dictionary of field names and their values to upsert.
            conflict_target (List[str]): A list of field names to use as the conflict target.

        Returns:
            object: The upserted model instance.
        """
        try:
            stmt = insert(model).values(fields)
            if conflict_target:
                stmt = stmt.on_conflict_do_update(index_elements=conflict_target, set_=fields)
            stmt = stmt.returning(model)
            result = self.session.execute(stmt).scalar_one()
            self.session.commit()
            return result
        except SQLAlchemyError as e:
            self.session.rollback()
            raise DatabaseException("Unable to upsert model") from e
