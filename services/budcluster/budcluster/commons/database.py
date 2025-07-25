from budmicroframe.commons.logging import get_logger
from budmicroframe.shared.psql_service import Database
from sqlalchemy import MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


logger = get_logger(__name__)


def get_engine():
    """Get database engine."""
    db = Database()
    db.connect()
    logger.info("Connected to postgres database")
    return db.engine


# Create sqlalchemy engine
engine = get_engine()

# Create session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Constraint naming convention to fix alembic autogenerate command issues
# NOTE: https://docs.sqlalchemy.org/en/20/core/constraints.html#constraint-naming-conventions
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata_obj = MetaData(naming_convention=convention)

# Base class for creating models
Base = declarative_base(metadata=metadata_obj)
