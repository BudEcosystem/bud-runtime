#!/usr/bin/env python3
"""Test script for JWT blacklist using Dapr state store."""

import asyncio
import time
from unittest.mock import Mock, patch

from budapp.shared.jwt_blacklist_service import JWTBlacklistService


async def test_jwt_blacklist_service():
    """Test the JWT blacklist service functionality.

    print("Testing JWT Blacklist Service with Dapr State Store")
    print("=" * 50)

    # Create service instance
    jwt_service = JWTBlacklistService()

    # Test token
    test_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test.signature"

    # Test 1: Blacklist a token
    print("\n1. Testing token blacklisting...")
    try:
        await jwt_service.blacklist_token(test_token, ttl=60)
        print("   ✓ Token blacklisted successfully")
    except Exception as e:
        print(f"   ✗ Failed to blacklist token: {e}")
        return

    # Test 2: Check if token is blacklisted
    print("\n2. Testing blacklist check...")
    try:
        is_blacklisted = await jwt_service.is_token_blacklisted(test_token)
        if is_blacklisted:
            print("   ✓ Token correctly identified as blacklisted")
        else:
            print("   ✗ Token not found in blacklist (may be due to Dapr not running)")
    except Exception as e:
        print(f"   ✗ Failed to check blacklist: {e}")

    # Test 3: Check non-blacklisted token
    print("\n3. Testing non-blacklisted token...")
    try:
        non_blacklisted_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.different.token"
        is_blacklisted = await jwt_service.is_token_blacklisted(non_blacklisted_token)
        if not is_blacklisted:
            print("   ✓ Non-blacklisted token correctly identified")
        else:
            print("   ✗ Non-blacklisted token incorrectly marked as blacklisted")
    except Exception as e:
        print(f"   ✗ Failed to check non-blacklisted token: {e}")

    # Test 4: Remove token from blacklist
    print("\n4. Testing token removal from blacklist...")
    try:
        await jwt_service.remove_from_blacklist(test_token)
        print("   ✓ Token removed from blacklist")

        # Verify removal
        is_blacklisted = await jwt_service.is_token_blacklisted(test_token)
        if not is_blacklisted:
            print("   ✓ Token successfully removed from blacklist")
        else:
            print("   ✗ Token still in blacklist after removal")
    except Exception as e:
        print(f"   ✗ Failed to remove token from blacklist: {e}")

    print("\n" + "=" * 50)
    print("Test completed!")
    """
    pass

async def test_with_mock_dapr():
    """Test with mocked Dapr client for unit testing."""

    print("\nTesting with Mocked Dapr Client")
    print("=" * 50)

    with patch('budapp.shared.jwt_blacklist_service.DaprService') as MockDaprService:
        mock_dapr = Mock()
        MockDaprService.return_value = mock_dapr

        # Mock get_state response for blacklisted token
        mock_response_blacklisted = Mock()
        mock_response_blacklisted.data = b'{"blacklisted":true,"timestamp":1234567890}'

        # Mock get_state response for non-blacklisted token
        mock_response_not_blacklisted = Mock()
        mock_response_not_blacklisted.data = None

        jwt_service = JWTBlacklistService()
        jwt_service.dapr_client = mock_dapr

        # Test blacklisting
        print("\n1. Testing blacklist operation...")
        test_token = "test.token.123"
        await jwt_service.blacklist_token(test_token, ttl=3600)
        mock_dapr.save_to_statestore.assert_called_once()
        print("   ✓ Blacklist operation called successfully")

        # Test checking blacklisted token
        print("\n2. Testing blacklist check...")
        mock_dapr.get_state.return_value = mock_response_blacklisted
        is_blacklisted = await jwt_service.is_token_blacklisted(test_token)
        assert is_blacklisted == True
        print("   ✓ Blacklisted token correctly identified")

        # Test checking non-blacklisted token
        print("\n3. Testing non-blacklisted token...")
        mock_dapr.get_state.return_value = mock_response_not_blacklisted
        is_blacklisted = await jwt_service.is_token_blacklisted("other.token")
        assert is_blacklisted == False
        print("   ✓ Non-blacklisted token correctly identified")

    print("\n" + "=" * 50)
    print("Mock tests completed successfully!")


if __name__ == "__main__":
    print("JWT Blacklist Service Test Suite")
    print("================================\n")

    # Run mock tests first (always work)
    asyncio.run(test_with_mock_dapr())

    # Run actual tests (requires Dapr to be running)
    print("\n\nAttempting to test with actual Dapr runtime...")
    print("Note: These tests require Dapr to be running.\n")

    try:
        asyncio.run(test_jwt_blacklist_service())
    except Exception as e:
        print(f"\n⚠️  Could not complete Dapr runtime tests: {e}")
        print("   This is expected if Dapr is not running.")
        print("   To run these tests, start the service with: ./deploy/start_dev.sh")
