#!/usr/bin/env python3
"""Test script to verify that new client users get a default project created."""

import asyncio
import os
import sys
from pathlib import Path


# Add the parent directory to the path
sys.path.append(str(Path(__file__).parent))

# Set environment variables before importing the app
os.environ["ENV"] = "dev"
os.environ["POSTGRES_DB"] = "budapp"
os.environ["POSTGRES_USER"] = "postgres"
os.environ["POSTGRES_PASSWORD"] = "postgres"
os.environ["POSTGRES_HOST"] = "localhost"
os.environ["POSTGRES_PORT"] = "5432"

import random
import string

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from budapp.auth.services import AuthService
from budapp.commons.constants import UserTypeEnum
from budapp.commons.database import get_db_url
from budapp.project_ops.crud import ProjectDataManager
from budapp.project_ops.models import Project as ProjectModel
from budapp.user_ops.crud import UserDataManager
from budapp.user_ops.models import User as UserModel
from budapp.user_ops.schemas import UserCreate


def generate_test_email():
    """Generate a random test email."""
    random_str = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"test_client_{random_str}@example.com"


async def test_client_project_creation():
    """Test that a new client user gets a default project."""
    # Create database session
    DATABASE_URL = get_db_url()
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    session = SessionLocal()

    try:
        # Create test user data
        test_email = generate_test_email()
        test_user = UserCreate(
            email=test_email,
            name="Test Client User",
            password="TestPassword123!",
            company="Test Company",
            user_type=UserTypeEnum.CLIENT,
        )

        print(f"Creating test client user with email: {test_email}")

        # Register the user
        auth_service = AuthService(session)
        db_user = await auth_service.register_user(test_user)

        print(f"User created successfully with ID: {db_user.id}")

        # Check if a default project was created
        projects = await ProjectDataManager(session).retrieve_all_by_fields(ProjectModel, {"created_by": db_user.id})

        if projects:
            print("✅ Success! Default project created for client user.")
            print("   Project details:")
            for project in projects:
                print(f"   - Name: {project.name}")
                print(f"   - Description: {project.description}")
                print(f"   - Status: {project.status}")
                print(f"   - Created by: {project.created_by}")

                # Check if user is associated with the project
                if db_user in project.users:
                    print("   - User is associated with the project ✅")
                else:
                    print("   - User is NOT associated with the project ❌")
        else:
            print("❌ No default project found for the client user!")

        # Test with non-client user type (should not create default project)
        test_email_admin = generate_test_email().replace("client", "admin")
        test_admin = UserCreate(
            email=test_email_admin,
            name="Test Admin User",
            password="TestPassword123!",
            company="Test Company",
            user_type=UserTypeEnum.ADMIN,
        )

        print(f"\nCreating test admin user with email: {test_email_admin}")
        db_admin = await auth_service.register_user(test_admin)

        admin_projects = await ProjectDataManager(session).retrieve_all_by_fields(
            ProjectModel, {"created_by": db_admin.id}
        )

        if admin_projects:
            print(f"❌ Admin user should NOT have a default project, but found {len(admin_projects)} projects!")
        else:
            print("✅ Correct! Admin user does not have a default project.")

    except Exception as e:
        print(f"Error during test: {e}")
        import traceback

        traceback.print_exc()
    finally:
        session.close()


if __name__ == "__main__":
    print("Testing Client Default Project Creation")
    print("=" * 50)
    asyncio.run(test_client_project_creation())
