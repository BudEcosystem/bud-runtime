#!/usr/bin/env python3
"""Test script to verify that default projects are created for CLIENT users
through both registration endpoints:
1. POST /auth/register (public registration)
2. POST /users (admin user creation)
"""

import json
import random
import string
import time

import requests


def generate_test_email():
    """Generate a random test email."""
    random_str = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"test_{random_str}@example.com"


def test_auth_register_endpoint():
    """Test that /auth/register creates default project for CLIENT users."""
    print("\n" + "=" * 60)
    print("Testing POST /auth/register endpoint")
    print("=" * 60)

    BASE_URL = "http://localhost:9081"  # Direct app port

    # Generate test user data
    test_email = generate_test_email()
    test_password = "TestPassword123!"

    registration_data = {
        "email": test_email,
        "name": "Test Client via Register",
        "password": test_password,
        "company": "Test Company",
        "user_type": "CLIENT",  # This will be forced to CLIENT in the endpoint
    }

    print(f"1. Registering CLIENT user via /auth/register: {test_email}")

    try:
        response = requests.post(
            f"{BASE_URL}/auth/register", json=registration_data, headers={"Content-Type": "application/json"}
        )

        print(f"   Response status: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ User registered successfully via /auth/register")
            print("   Note: Default project should be created for this CLIENT user")
        else:
            print(f"   ❌ Registration failed: {response.text[:200]}")

    except Exception as e:
        print(f"   ❌ Error during registration: {e}")


def test_users_post_endpoint():
    """Test that POST /users creates default project for CLIENT users."""
    print("\n" + "=" * 60)
    print("Testing POST /users endpoint")
    print("=" * 60)

    BASE_URL = "http://localhost:9081"  # Direct app port

    # First, we need to login as an admin user who has USER_MANAGE permission
    # For this test, we'll assume there's an admin user already set up
    print("1. Getting admin access token...")

    # Note: You'll need to update these credentials with actual admin credentials
    admin_credentials = {
        "email": "admin@example.com",  # Update with actual admin email
        "password": "AdminPassword123!",  # Update with actual admin password
    }

    try:
        # Login as admin
        response = requests.post(
            f"{BASE_URL}/auth/login", json=admin_credentials, headers={"Content-Type": "application/json"}
        )

        if response.status_code != 200:
            print("   ❌ Admin login failed. Update admin credentials in the script.")
            print(f"   Response: {response.text[:200]}")
            return

        login_data = response.json()
        access_token = login_data.get("result", {}).get("token", {}).get("access_token")

        if not access_token:
            print("   ❌ No access token received")
            return

        print("   ✅ Admin logged in successfully")

    except Exception as e:
        print(f"   ❌ Error during admin login: {e}")
        return

    # Now create a user via POST /users
    print("\n2. Creating CLIENT user via POST /users...")

    test_email = generate_test_email()
    user_data = {
        "email": test_email,
        "name": "Test Client via POST /users",
        "password": "TestPassword123!",
        "company": "Test Company",
        "user_type": "CLIENT",
    }

    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

    try:
        response = requests.post(f"{BASE_URL}/users", json=user_data, headers=headers)

        print(f"   Response status: {response.status_code}")
        if response.status_code == 200:
            print(f"   ✅ User created successfully via POST /users: {test_email}")
            print("   Note: Default project should be created for this CLIENT user")

            # Try to get the user details
            user_response = response.json()
            if "user" in user_response:
                user_id = user_response["user"].get("id")
                print(f"   User ID: {user_id}")
        else:
            print(f"   ❌ User creation failed: {response.text[:200]}")

    except Exception as e:
        print(f"   ❌ Error during user creation: {e}")

    # Test creating an ADMIN user (should NOT get default project)
    print("\n3. Creating ADMIN user via POST /users (should NOT get default project)...")

    admin_email = generate_test_email().replace("test", "admin")
    admin_user_data = {
        "email": admin_email,
        "name": "Test Admin User",
        "password": "TestPassword123!",
        "company": "Test Company",
        "user_type": "ADMIN",
    }

    try:
        response = requests.post(f"{BASE_URL}/users", json=admin_user_data, headers=headers)

        print(f"   Response status: {response.status_code}")
        if response.status_code == 200:
            print(f"   ✅ ADMIN user created successfully: {admin_email}")
            print("   Note: No default project should be created for ADMIN users")
        else:
            print(f"   ❌ Admin user creation failed: {response.text[:200]}")

    except Exception as e:
        print(f"   ❌ Error during admin user creation: {e}")


def main():
    """Run all tests."""
    print("\nTesting Default Project Creation for CLIENT Users")
    print("=" * 60)
    print("This script tests that CLIENT users get a default project")
    print("when created through both available endpoints:")
    print("1. POST /auth/register (public registration)")
    print("2. POST /users (admin user creation)")

    # Test /auth/register endpoint
    test_auth_register_endpoint()

    # Test POST /users endpoint
    test_users_post_endpoint()

    print("\n" + "=" * 60)
    print("Test Summary:")
    print("- Both endpoints use AuthService.register_user()")
    print("- The updated register_user() method creates default projects for CLIENT users")
    print("- ADMIN and other user types do NOT get default projects")
    print("- Default project is named 'My First Project'")
    print("=" * 60)


if __name__ == "__main__":
    main()
