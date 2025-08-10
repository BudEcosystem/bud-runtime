#!/usr/bin/env python3
"""Manual testing script for project_type filtering feature."""

import asyncio
import json
import os
from datetime import datetime

import httpx
from dotenv import load_dotenv


# Load environment variables
load_dotenv()

# Configuration
BASE_URL = os.getenv("BASE_URL", "http://localhost:8005")
AUTH_ENDPOINT = f"{BASE_URL}/auth/login"
PROJECTS_ENDPOINT = f"{BASE_URL}/projects/"

# Test credentials (update these with valid test credentials)
TEST_EMAIL = os.getenv("TEST_EMAIL", "admin@example.com")
TEST_PASSWORD = os.getenv("TEST_PASSWORD", "admin123")


async def get_auth_token():
    """Authenticate and get access token."""
    async with httpx.AsyncClient() as client:
        response = await client.post(AUTH_ENDPOINT, json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
        if response.status_code == 200:
            data = response.json()
            return data.get("access_token")
        else:
            print(f"Authentication failed: {response.status_code}")
            print(response.text)
            return None


async def test_project_filters(token):
    """Test various project filter combinations."""
    headers = {"Authorization": f"Bearer {token}"}

    test_cases = [
        {"name": "No filters (all projects)", "params": {}, "description": "Should return all active projects"},
        {
            "name": "Filter by CLIENT_APP type",
            "params": {"project_type": "client_app"},
            "description": "Should return only client application projects",
        },
        {
            "name": "Filter by ADMIN_APP type",
            "params": {"project_type": "admin_app"},
            "description": "Should return only admin application projects",
        },
        {
            "name": "Combined filters (name + type)",
            "params": {"name": "test", "project_type": "client_app"},
            "description": "Should return client projects with 'test' in name",
        },
        {
            "name": "Filter with pagination",
            "params": {"project_type": "admin_app", "page": 1, "limit": 5},
            "description": "Should return paginated admin projects",
        },
        {
            "name": "Filter with sorting",
            "params": {"project_type": "client_app", "order_by": "-created_at"},
            "description": "Should return client projects sorted by creation date (desc)",
        },
        {
            "name": "Invalid project_type",
            "params": {"project_type": "invalid_type"},
            "description": "Should return validation error (422)",
        },
    ]

    async with httpx.AsyncClient() as client:
        print("\n" + "=" * 80)
        print("TESTING PROJECT TYPE FILTERING")
        print("=" * 80)

        for i, test_case in enumerate(test_cases, 1):
            print(f"\n[Test {i}] {test_case['name']}")
            print(f"Description: {test_case['description']}")
            print(f"Parameters: {test_case['params']}")

            try:
                response = await client.get(
                    PROJECTS_ENDPOINT, params=test_case["params"], headers=headers, timeout=10.0
                )

                print(f"Status Code: {response.status_code}")

                if response.status_code == 200:
                    data = response.json()
                    print(f"Total Records: {data.get('total_record', 0)}")
                    print(f"Page: {data.get('page', 1)}, Limit: {data.get('limit', 10)}")

                    if "projects" in data and data["projects"]:
                        print("Sample Projects:")
                        for project in data["projects"][:3]:  # Show first 3 projects
                            print(f"  - {project['name']} (Type: {project.get('project_type', 'N/A')})")
                    else:
                        print("  No projects found")

                elif response.status_code == 422:
                    print("Validation Error (Expected for invalid inputs):")
                    error_data = response.json()
                    print(f"  {json.dumps(error_data, indent=2)}")
                else:
                    print(f"Unexpected response: {response.text[:200]}")

            except Exception as e:
                print(f"Error: {str(e)}")

            print("-" * 40)


async def create_test_projects(token):
    """Create test projects with different types (optional helper)."""
    headers = {"Authorization": f"Bearer {token}"}

    test_projects = [
        {
            "name": f"Test Client App {datetime.now().strftime('%H%M%S')}",
            "description": "Test client application project",
            "project_type": "client_app",
        },
        {
            "name": f"Test Admin App {datetime.now().strftime('%H%M%S')}",
            "description": "Test admin application project",
            "project_type": "admin_app",
        },
    ]

    async with httpx.AsyncClient() as client:
        print("\n" + "=" * 80)
        print("CREATING TEST PROJECTS")
        print("=" * 80)

        for project_data in test_projects:
            print(f"\nCreating: {project_data['name']}")

            try:
                response = await client.post(PROJECTS_ENDPOINT, json=project_data, headers=headers, timeout=10.0)

                if response.status_code in [200, 201]:
                    data = response.json()
                    print(f"  ✓ Created successfully (ID: {data.get('project', {}).get('id', 'N/A')})")
                else:
                    print(f"  ✗ Failed: {response.status_code}")
                    print(f"    {response.text[:200]}")

            except Exception as e:
                print(f"  ✗ Error: {str(e)}")


async def main():
    """Run all tests."""
    print("Starting Project Type Filter Testing")
    print(f"Target: {BASE_URL}")
    print(f"Test User: {TEST_EMAIL}")

    # Get authentication token
    print("\nAuthenticating...")
    token = await get_auth_token()

    if not token:
        print("Failed to authenticate. Please check credentials.")
        return

    print("✓ Authentication successful")

    # Optionally create test projects
    create_projects = input("\nCreate test projects? (y/n): ").lower().strip() == "y"
    if create_projects:
        await create_test_projects(token)

    # Run filter tests
    await test_project_filters(token)

    print("\n" + "=" * 80)
    print("TESTING COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
