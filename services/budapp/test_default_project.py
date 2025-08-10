#!/usr/bin/env python3
"""Integration test for default project creation for CLIENT users.
This test verifies that when a new user with user_type=CLIENT is registered,
a default project is automatically created and associated with them.
"""

import json
import random
import string
import time

import requests


def generate_test_email():
    """Generate a random test email."""
    random_str = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"test_client_{random_str}@example.com"


def test_client_registration_with_default_project():
    """Test that client users get a default project upon registration."""
    BASE_URL = "http://localhost:3510"

    # Generate test user data
    test_email = generate_test_email()
    test_password = "TestPassword123!"

    registration_data = {
        "email": test_email,
        "name": "Test Client User",
        "password": test_password,
        "company": "Test Company",
        "user_type": "CLIENT",  # This will be forced to CLIENT in the endpoint anyway
    }

    print("Testing default project creation for CLIENT users")
    print("=" * 60)
    print(f"1. Registering new CLIENT user: {test_email}")

    # Register the user
    try:
        response = requests.post(
            f"{BASE_URL}/auth/register", json=registration_data, headers={"Content-Type": "application/json"}
        )

        if response.status_code == 200:
            print("   ✅ User registered successfully")
        else:
            print(f"   ❌ Registration failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return

    except Exception as e:
        print(f"   ❌ Error during registration: {e}")
        return

    # Wait a moment for async operations to complete
    time.sleep(2)

    print("\n2. Logging in as the new user...")

    # Login to get access token
    login_data = {"email": test_email, "password": test_password}

    try:
        response = requests.post(
            f"{BASE_URL}/auth/login", json=login_data, headers={"Content-Type": "application/json"}
        )

        if response.status_code == 200:
            login_response = response.json()
            access_token = login_response.get("result", {}).get("token", {}).get("access_token")
            if access_token:
                print("   ✅ Login successful")
            else:
                print("   ❌ Login succeeded but no access token found")
                print(f"   Response: {json.dumps(login_response, indent=2)}")
                return
        else:
            print(f"   ❌ Login failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return

    except Exception as e:
        print(f"   ❌ Error during login: {e}")
        return

    print("\n3. Fetching user's projects...")

    # Get user's projects
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

    try:
        response = requests.get(f"{BASE_URL}/projects", headers=headers, params={"page": 1, "limit": 10})

        if response.status_code == 200:
            projects_response = response.json()
            projects = projects_response.get("result", [])

            if projects:
                print(f"   ✅ Found {len(projects)} project(s) for the user")
                for i, project in enumerate(projects, 1):
                    print(f"\n   Project {i}:")
                    print(f"   - Name: {project.get('name')}")
                    print(f"   - Description: {project.get('description')}")
                    print(f"   - Status: {project.get('status')}")
                    print(f"   - ID: {project.get('id')}")

                # Check if the default project is present
                default_project = next((p for p in projects if "My First Project" in p.get("name", "")), None)

                if default_project:
                    print("\n   ✅ SUCCESS: Default project 'My First Project' was created!")
                else:
                    print("\n   ⚠️  Projects found but none match the default project name")
            else:
                print("   ❌ No projects found for the user")
                print(f"   Response: {json.dumps(projects_response, indent=2)}")
        else:
            print(f"   ❌ Failed to fetch projects: {response.status_code}")
            print(f"   Response: {response.text}")

    except Exception as e:
        print(f"   ❌ Error fetching projects: {e}")

    print("\n" + "=" * 60)
    print("Test completed!")


if __name__ == "__main__":
    test_client_registration_with_default_project()
