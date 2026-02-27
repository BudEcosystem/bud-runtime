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

"""Provides utility functions for managing the database connection."""

import os

from alembic import command
from alembic.config import Config
from budmicroframe.shared.psql_service import PSQLBase, TimestampMixin  # noqa: F401
from pydantic import PostgresDsn
from sqlalchemy import Engine, MetaData, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from . import logging
from .config import app_settings, secrets_settings


logger = logging.get_logger(__name__)


def get_engine() -> Engine:
    """Create and return a SQLAlchemy engine instance.

    This function initializes a new SQLAlchemy engine using the PostgreSQL
    connection URL specified in the application settings. The engine is
    configured with echo=True for SQL query logging.

    Returns:
        Engine: A SQLAlchemy Engine instance connected to the PostgreSQL database.

    Raises:
        SQLAlchemyError: If there's an error creating the engine or connecting to the database.
    """
    postgres_url = PostgresDsn.build(
        scheme="postgresql+psycopg",
        username=secrets_settings.psql_user,
        password=secrets_settings.psql_password,
        host=app_settings.psql_host,
        port=app_settings.psql_port,
        path=app_settings.psql_dbname,
    ).__str__()

    return create_engine(
        postgres_url,
        pool_size=30,  # Increased from 20
        max_overflow=60,  # Increased from 40 (total: 90)
        pool_pre_ping=True,  # Verify connections before using them
        pool_recycle=3600,  # Recycle connections after 1 hour
        pool_timeout=10,  # Fail fast instead of hanging when pool exhausted
        echo_pool=True,  # Enable pool logging for debugging
    )


# Create sqlalchemy engine
engine = get_engine()

# Create session class with proper configuration
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,  # Prevent unnecessary database hits after commit
)

# Constraint naming convention to fix alembic autogenerate command issues
# https://docs.sqlalchemy.org/en/20/core/constraints.html#constraint-naming-conventions
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata_obj = MetaData(naming_convention=convention)

# Create base class for creating models
Base = declarative_base(metadata=metadata_obj)
Base = PSQLBase


def run_migrations() -> None:
    """Run Alembic migrations on application startup.

    This function executes Alembic database migrations to bring the database
    schema up to the latest version. It uses the configuration file specified
    in the application settings.

    The function performs the following steps:
    1. Constructs the path to the Alembic configuration file.
    2. Creates an Alembic Config object with the configuration file.
    3. Runs the upgrade command to apply all pending migrations.

    Raises:
        FileNotFoundError: If the Alembic configuration file is not found.
        alembic.util.exc.CommandError: If there's an error during migration.

    Note:
        This function should be called during application startup to ensure
        the database schema is up to date before the application begins
        serving requests.
    """
    logger.info("Starting database migrations")

    alembic_cfg_file = os.path.join(app_settings.base_dir, "budapp", "alembic.ini")

    if not os.path.exists(alembic_cfg_file):
        logger.error(f"Alembic configuration file not found: {alembic_cfg_file}")
        raise FileNotFoundError(f"Alembic configuration file not found: {alembic_cfg_file}")

    try:
        alembic_cfg = Config(alembic_cfg_file)
        command.upgrade(alembic_cfg, "head")
        logger.info("Database migrations completed successfully")
    except Exception as e:
        logger.error(f"Error occurred during database migration: {str(e)}")
        raise
