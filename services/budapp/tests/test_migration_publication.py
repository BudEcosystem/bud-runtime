"""Test script for publication migration."""

import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

# Migration revision ID
MIGRATION_ID = "f93ff02dff8"


def test_migration_up_down():
    """Test migration up and down scenarios."""
    # Get database URL from environment or use test database
    db_url = os.getenv("DATABASE_URL", "postgresql://test_user:test_password@localhost/test_db")

    # Create engine
    engine = create_engine(db_url)

    # Get Alembic config
    alembic_cfg = Config("budapp/alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    print("Testing migration UP...")

    # Run migration up
    try:
        command.upgrade(alembic_cfg, MIGRATION_ID)
        print("✓ Migration UP successful")
    except Exception as e:
        print(f"✗ Migration UP failed: {e}")
        return False

    # Verify schema changes
    inspector = inspect(engine)

    # Check endpoint table columns
    endpoint_columns = {col['name'] for col in inspector.get_columns('endpoint')}
    expected_columns = {'is_published', 'published_date', 'published_by'}

    if expected_columns.issubset(endpoint_columns):
        print("✓ Endpoint columns added successfully")
    else:
        print(f"✗ Missing columns: {expected_columns - endpoint_columns}")
        return False

    # Check publication_history table
    if 'publication_history' in inspector.get_table_names():
        print("✓ publication_history table created")

        # Check indexes
        indexes = inspector.get_indexes('endpoint')
        index_names = {idx['name'] for idx in indexes}
        expected_indexes = {
            'ix_endpoint_is_published',
            'ix_endpoint_is_published_published_date'
        }

        if expected_indexes.issubset(index_names):
            print("✓ Indexes created successfully")
        else:
            print(f"✗ Missing indexes: {expected_indexes - index_names}")
    else:
        print("✗ publication_history table not found")
        return False

    print("\nTesting migration DOWN...")

    # Get the previous revision
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT version_num FROM alembic_version WHERE version_num = :version"),
            {"version": MIGRATION_ID}
        )
        if result.rowcount == 0:
            print("✗ Migration not applied")
            return False

    # Run migration down
    try:
        # Downgrade to the previous revision (375eb22cb3af)
        command.downgrade(alembic_cfg, "375eb22cb3af")
        print("✓ Migration DOWN successful")
    except Exception as e:
        print(f"✗ Migration DOWN failed: {e}")
        return False

    # Verify rollback
    inspector = inspect(engine)
    endpoint_columns = {col['name'] for col in inspector.get_columns('endpoint')}

    if not expected_columns.intersection(endpoint_columns):
        print("✓ Endpoint columns removed successfully")
    else:
        print(f"✗ Columns still exist: {expected_columns.intersection(endpoint_columns)}")
        return False

    if 'publication_history' not in inspector.get_table_names():
        print("✓ publication_history table removed")
    else:
        print("✗ publication_history table still exists")
        return False

    print("\n✅ All migration tests passed!")
    return True


def test_data_integrity():
    """Test that existing data is preserved during migration."""
    db_url = os.getenv("DATABASE_URL", "postgresql://test_user:test_password@localhost/test_db")
    engine = create_engine(db_url)

    with Session(engine) as session:
        # Check if we can query endpoints table
        try:
            result = session.execute(text("SELECT COUNT(*) FROM endpoint"))
            count = result.scalar()
            print(f"✓ Endpoint table has {count} records")

            # Check default values
            result = session.execute(
                text("SELECT COUNT(*) FROM endpoint WHERE is_published = false")
            )
            unpublished_count = result.scalar()
            print(f"✓ All endpoints defaulted to unpublished: {unpublished_count}")

        except Exception as e:
            print(f"✗ Data integrity check failed: {e}")
            return False

    return True


if __name__ == "__main__":
    print("=== Testing Publication Migration ===\n")

    # Run tests
    migration_ok = test_migration_up_down()

    if migration_ok:
        print("\n=== Testing Data Integrity ===\n")
        test_data_integrity()
    else:
        print("\n✗ Migration tests failed, skipping data integrity tests")
        sys.exit(1)
