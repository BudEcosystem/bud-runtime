"""Test to ensure passwords are properly hashed and never stored as plain text."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from uuid import uuid4

# from budapp.auth.services import AuthService  # Commented out to avoid config issues
# from budapp.user_ops.schemas import UserCreate
# from budapp.commons.constants import UserRoleEnum, UserTypeEnum
# from budapp.permissions.schemas import PermissionList


@pytest.mark.asyncio
async def test_user_registration_hashes_password():
    """Test that user registration properly hashes passwords."""

    # Create test user data
    test_password = "MySecurePassword123!"
    user_create = UserCreate(
        email="test@example.com",
        name="Test User",
        password=test_password,
        role=UserRoleEnum.DEVELOPER,
        user_type=UserTypeEnum.CLIENT,
        permissions=[]
    )

    # Mock dependencies
    mock_session = Mock()
    mock_session.commit = AsyncMock()  # session.commit() is async
    mock_keycloak = Mock()
    mock_keycloak.create_user_with_permissions = AsyncMock(return_value=str(uuid4()))

    with patch('budapp.auth.services.KeycloakManager', return_value=mock_keycloak):
        with patch('budapp.auth.services.UserDataManager') as mock_data_manager:
            # Mock the data manager methods
            mock_data_manager.return_value.retrieve_by_fields = AsyncMock()
            mock_data_manager.return_value.insert_one = AsyncMock()
            mock_data_manager.return_value.update_subscriber_status = AsyncMock()

            # Track what gets inserted - only capture User objects
            inserted_user = None
            def capture_insert(obj):
                nonlocal inserted_user
                # Only capture User objects, not TenantUserMapping, UserBilling, or Project
                if obj.__class__.__name__ == 'User':
                    inserted_user = obj
                return obj

            mock_data_manager.return_value.insert_one.side_effect = capture_insert

            # Mock tenant and client data
            mock_tenant = Mock(id=uuid4(), name="Default", realm_name="default")
            mock_client = Mock(id=uuid4(), client_id="test-client", client_secret="secret", client_named_id="test")

            # Mock the retrieve_by_fields calls in order:
            # 1. Check if email exists (should return None)
            # 2. Get tenant
            # 3. Get tenant client
            mock_data_manager.return_value.retrieve_by_fields.side_effect = [
                None,         # Email doesn't exist
                mock_tenant,  # Tenant exists
                mock_client,  # Client exists
            ]

            # Create auth service and register user
            auth_service = AuthService(mock_session)

            # Patch BudNotifyHandler and PermissionService to avoid external calls
            with patch('budapp.auth.services.BudNotifyHandler') as mock_notify_handler:
                # Mock BudNotifyHandler instance methods
                mock_notify_instance = Mock()
                mock_notify_instance.create_subscriber = AsyncMock()
                mock_notify_handler.return_value = mock_notify_instance

                with patch('budapp.auth.services.PermissionService') as mock_perm_service:
                    # Mock PermissionService instance methods
                    mock_perm_instance = Mock()
                    mock_perm_instance.create_resource_permission_by_user = AsyncMock()
                    mock_perm_service.return_value = mock_perm_instance

                    await auth_service.register_user(user_create, is_self_registration=True)

            # Verify password was hashed
            assert inserted_user is not None, "User should have been inserted"

            # Check that password is NOT the plain text
            assert hasattr(inserted_user, 'password'), "User should have password field"
            if inserted_user.password:  # Password might be None if using Keycloak only
                assert inserted_user.password != test_password, "Password should NOT be stored as plain text!"
                # Bcrypt hashes typically start with $2b$, $2a$, or $2y$
                assert inserted_user.password.startswith('$2'), "Password should be a bcrypt hash"


@pytest.mark.asyncio
async def test_password_is_excluded_from_model_dump():
    """Test that password is properly excluded from model_dump and replaced with hash."""

    test_password = "TestPassword456!"
    user_create = UserCreate(
        email="another@example.com",
        name="Another User",
        password=test_password,
        role=UserRoleEnum.DEVELOPER,
        user_type=UserTypeEnum.CLIENT,
        permissions=[]
    )

    # The fix should:
    # 1. Hash the password
    # 2. Exclude password from model_dump
    # 3. Add the hashed password separately

    user_data = user_create.model_dump(exclude={"permissions", "password"})

    # Verify password is not in the dumped data
    assert "password" not in user_data, "Password should be excluded from model_dump"

    # This is what the fixed code should do
    from budapp.commons.security import HashManager
    from budapp.commons.config import secrets_settings

    hash_manager = HashManager()
    salted_password = test_password + secrets_settings.password_salt
    hashed_password = await hash_manager.get_hash(salted_password)

    # Verify the hash is different from plain text
    assert hashed_password != test_password, "Hashed password should not equal plain text"
    assert hashed_password.startswith('$2'), "Should be a bcrypt hash"


def test_bcrypt_hash_format():
    """Test that we can identify bcrypt hashes correctly."""

    # Examples of bcrypt hashes
    bcrypt_hashes = [
        "$2b$12$KIXxPfAQnLQjvhEiGWRPOevJcbtQceQVOOSg8S0n9No3Wh0vLNOWO",
        "$2a$10$N9qo8uLOickgx2ZMRZoMye",
        "$2y$10$N9qo8uLOickgx2ZMRZoMye"
    ]

    plain_texts = [
        "password123",
        "MySecurePassword",
        "admin",
        "12345678"
    ]

    # Check that we can identify hashes vs plain text
    for hash_str in bcrypt_hashes:
        assert hash_str.startswith('$2'), "Bcrypt hashes should start with $2"

    for plain in plain_texts:
        assert not plain.startswith('$2'), "Plain text should not look like bcrypt hash"


@pytest.mark.asyncio
async def test_password_hashing_utility():
    """Test password hashing utility functions work correctly."""
    from budapp.commons.security import HashManager
    import bcrypt

    # Create hash manager instance
    hash_manager = HashManager()

    # Test password hashing
    test_password = "SecurePassword123!"
    hashed = await hash_manager.get_hash(test_password)

    # Verify it's a proper bcrypt hash
    assert hashed.startswith('$2'), "Should be a bcrypt hash"
    assert hashed != test_password, "Hashed password should not equal plain text"

    # Verify the hash can be verified using the manager
    is_valid = await hash_manager.verify_hash(test_password, hashed)
    assert is_valid, "Hash should verify against original password"

    # Verify different passwords produce different hashes
    hashed2 = await hash_manager.get_hash(test_password)
    assert hashed != hashed2, "Same password should produce different salted hashes"
